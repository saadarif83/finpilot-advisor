"""
Approvals service: the human side of every money movement.

  draft --(advisor: send to client)--> pending_client
  pending_client --(client approves on phone)--> pending_supervisor | executed
  pending_supervisor --(supervisor co-signs)--> executed
  (any decline -> declined; executor problem -> failed)

Each approval is an HMAC signature over the proposal's frozen args hash.
"""
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.config import settings
from app.identity import current_employee, require_role, issue_client_approval_token, verify_client_approval_token
from app.proposals import store
from app.proposals.executor import execute, ExecutionRefused
from app.gateway import events
from app import audit

router = APIRouter(tags=["proposals"])


def _get(pid: str) -> dict:
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "Proposal not found")
    return p


def _run_executor(p: dict, actor: dict | None):
    try:
        result = execute(p)
        events.record("admin", "info" if result.get("ok") else "denied", employee=actor, client_id=p["client_id"],
                      detail=f"Executor: proposal {p['id']} " + ("EXECUTED" if result.get("ok") else f"FAILED ({result.get('error')}) — compensated"))
    except ExecutionRefused as e:
        p["status"] = "failed"
        p["execution"] = {"ok": False, "error": f"Refused: {e}"}
        store.add_history(p, "refused", "Executor", str(e))
        audit.add_proposal_event(p["audit_id"], {"proposal_id": p["id"], "event": "execution_refused", "detail": str(e)})
        events.record("admin", "denied", employee=actor, client_id=p["client_id"], detail=f"Executor REFUSED proposal {p['id']}: {e}")


# ------------------------------------------------------------ employee side

@router.get("/proposals")
def list_proposals(employee: dict = Depends(current_employee)):
    require_role(employee, "advisor", "supervisor", "compliance")
    return {"proposals": store.all_proposals(), "cosign_threshold": settings.COSIGN_THRESHOLD}


@router.get("/proposals/{pid}")
def get_proposal(pid: str, employee: dict = Depends(current_employee)):
    require_role(employee, "advisor", "supervisor", "compliance")
    return _get(pid)


@router.post("/proposals/{pid}/send")
def send_to_client(pid: str, employee: dict = Depends(current_employee)):
    require_role(employee, "advisor", "supervisor")
    p = _get(pid)
    if p["status"] not in ("draft", "pending_client"):
        raise HTTPException(400, f"Proposal is {p['status']}")
    token = issue_client_approval_token(p["id"], p["client_id"], p["args_hash"])
    p["approval_url"] = f"{settings.FRONTEND_ORIGIN}/approve/{p['id']}?t={token}"
    if p["status"] == "draft":
        p["status"] = "pending_client"
        store.add_history(p, "sent_to_client", employee["name"], "Approval request sent to the client's device")
        audit.add_proposal_event(p["audit_id"], {"proposal_id": p["id"], "event": "sent_to_client", "by": employee["username"]})
        events.record("admin", "info", employee=employee, client_id=p["client_id"],
                      detail=f"Proposal {p['id']} sent to client for approval")
    return p


@router.post("/proposals/{pid}/discard")
def discard(pid: str, employee: dict = Depends(current_employee)):
    require_role(employee, "advisor", "supervisor")
    p = _get(pid)
    if p["status"] not in ("draft", "pending_client"):
        raise HTTPException(400, f"Proposal is {p['status']}")
    p["status"] = "discarded"
    store.add_history(p, "discarded", employee["name"])
    return p


class Decision(BaseModel):
    decision: str  # approved | declined


@router.post("/proposals/{pid}/cosign")
def cosign(pid: str, body: Decision, employee: dict = Depends(current_employee)):
    require_role(employee, "supervisor")
    p = _get(pid)
    if p["status"] != "pending_supervisor":
        raise HTTPException(400, f"Proposal is {p['status']}, not awaiting a co-sign")
    if employee["username"] == p["created_by"]:
        raise HTTPException(403, "Maker-checker: you cannot co-sign a proposal you prepared")
    approval = {"by": employee["username"], "name": employee["name"], "role": "supervisor", "decision": body.decision, "at": time.time()}
    approval["signature"] = store.sign(p, approval["by"], approval["role"])
    p["approvals"].append(approval)
    audit.add_proposal_event(p["audit_id"], {"proposal_id": p["id"], "event": f"supervisor_{body.decision}", "by": employee["username"]})
    if body.decision != "approved":
        p["status"] = "declined"
        store.add_history(p, "declined", employee["name"], "Supervisor declined")
        return p
    store.add_history(p, "cosigned", employee["name"], f"Signed hash {p['args_hash'][:12]}…")
    _run_executor(p, employee)
    return p


@router.post("/proposals/{pid}/demo-tamper")
def demo_tamper(pid: str, employee: dict = Depends(current_employee)):
    """DEMO ONLY: simulate an attacker (or a bug) changing the amount after the
    client approved. The executor must refuse, because the hash no longer matches."""
    p = _get(pid)
    if p["status"] != "pending_supervisor":
        raise HTTPException(400, "Tampering demo works on a proposal awaiting supervisor co-sign")
    old = p["params"]["amount"]
    p["params"] = {**p["params"], "amount": round(float(old) * 10, 2)}
    store.add_history(p, "tampered", "⚠ Simulated attacker", f"Amount changed {old} → {p['params']['amount']} after client approval")
    events.record("admin", "flagged", employee=employee, client_id=p["client_id"],
                  detail=f"DEMO: proposal {p['id']} amount altered after approval ({old} → {p['params']['amount']})")
    return p


# ------------------------------------------------------------ client side (phone)

@router.get("/client-approval/{pid}")
def client_view(pid: str, t: str):
    claims = verify_client_approval_token(t)
    p = _get(pid)
    if claims["proposal_id"] != pid or claims["sub"] != p["client_id"]:
        raise HTTPException(403, "This link is not for this proposal")
    view = store.client_view(p)
    view["link_matches"] = claims["args_hash"] == p["args_hash"]
    return view


class ClientDecision(BaseModel):
    t: str
    decision: str  # approved | declined


@router.post("/client-approval/{pid}")
def client_decide(pid: str, body: ClientDecision):
    claims = verify_client_approval_token(body.t)
    p = _get(pid)
    if claims["proposal_id"] != pid or claims["sub"] != p["client_id"]:
        raise HTTPException(403, "This link is not for this proposal")
    if claims["args_hash"] != p["args_hash"]:
        raise HTTPException(409, "This proposal changed after the link was issued. Please ask your advisor for a new link.")
    if p["status"] != "pending_client":
        raise HTTPException(400, f"This request is already {p['status'].replace('_', ' ')}")
    approval = {"by": p["client_id"], "name": p["client_name"], "role": "client", "decision": body.decision, "at": time.time()}
    approval["signature"] = store.sign(p, approval["by"], approval["role"])
    p["approvals"].append(approval)
    audit.add_proposal_event(p["audit_id"], {"proposal_id": p["id"], "event": f"client_{body.decision}", "by": p["client_name"]})
    events.record("admin", "info", client_id=p["client_id"],
                  detail=f"Client {body.decision} proposal {p['id']} on their device (signed hash {p['args_hash'][:10]}…)")
    if body.decision != "approved":
        p["status"] = "declined"
        store.add_history(p, "declined", p["client_name"], "Client declined")
        return store.client_view(p)
    store.add_history(p, "client_approved", p["client_name"], f"Signed hash {p['args_hash'][:12]}…")
    if p["needs_cosign"]:
        p["status"] = "pending_supervisor"
        store.add_history(p, "awaiting_cosign", "Approvals service", f"Above ${settings.COSIGN_THRESHOLD:,.0f} — supervisor co-sign required")
    else:
        _run_executor(p, None)
    return store.client_view(p)
