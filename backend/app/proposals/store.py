"""
Proposals: what the model suggested, frozen into an exact, hashable action.

The moment a proposal tool returns a plan, the gateway freezes its exact
parameters (client, source account, destination, amount) and computes a
SHA-256 hash of them. Every approval signs THAT hash. The executor refuses
to run anything whose parameters no longer match the hash that was signed —
so "approve $4,812" can never turn into "execute $48,120".
"""
import hashlib
import hmac
import json
import time
from app.config import settings

_proposals: dict[str, dict] = {}
_seq = 0


def args_hash(ptype: str, params: dict) -> str:
    canonical = json.dumps({"type": ptype, "params": params}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def sign(proposal: dict, approver: str, role: str) -> str:
    msg = f"{proposal['id']}|{proposal['args_hash']}|{approver}|{role}".encode()
    return hmac.new(settings.APPROVAL_SIGNING_KEY.encode(), msg, hashlib.sha256).hexdigest()


def verify_signature(proposal: dict, approval: dict) -> bool:
    expected = sign(proposal, approval["by"], approval["role"])
    return hmac.compare_digest(expected, approval["signature"])


def create_from_plan(plan: dict, *, employee: dict, client: dict, audit_id: str) -> dict:
    global _seq
    _seq += 1
    pid = f"P-{_seq:04d}"
    amount = float(plan["params"]["amount"])
    p = {
        "id": pid,
        "audit_id": audit_id,
        "type": plan["type"],
        "title": plan["title"],
        "client_id": client["client_id"],
        "client_name": client["name"],
        "created_by": employee["username"],
        "created_by_name": employee["name"],
        "created_at": time.time(),
        "params": plan["params"],
        "summary": plan.get("summary", {}),
        "rationale": plan.get("rationale", ""),
        "checks": plan.get("checks", []),
        "amount": amount,
        "needs_cosign": amount > settings.COSIGN_THRESHOLD,
        "args_hash": args_hash(plan["type"], plan["params"]),
        "status": "draft",
        "approvals": [],
        "history": [{"at": time.time(), "event": "proposed", "by": "AI copilot", "detail": f"Prepared for {employee['name']}"}],
        "execution": None,
    }
    _proposals[pid] = p
    return p


def get(pid: str) -> dict | None:
    return _proposals.get(pid)


def all_proposals() -> list[dict]:
    return sorted(_proposals.values(), key=lambda p: -p["created_at"])


def add_history(p: dict, event: str, by: str, detail: str = ""):
    p["history"].append({"at": time.time(), "event": event, "by": by, "detail": detail})


def client_view(p: dict) -> dict:
    """What the client sees on their phone — no internal checks or employee details beyond the advisor's name."""
    return {k: p[k] for k in ("id", "type", "title", "client_name", "created_by_name", "amount", "rationale", "status", "args_hash", "needs_cosign")} | {
        "summary": p["summary"]}


def reset():
    global _seq
    _proposals.clear()
    _seq = 0
