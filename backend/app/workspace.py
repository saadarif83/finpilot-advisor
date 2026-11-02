"""
Screens' data (backend-for-frontend). Humans viewing a client in the UI are
governed by the same ROLE policy as the AI. Client CONSENT only governs AI
use, so an advisor can still see Marco's wealth accounts on screen even
though the copilot cannot.
"""
from fastapi import APIRouter, Depends, HTTPException
from app.identity import current_employee
from app import state, policy
from app.data_seed import PERFORMANCE_MONTHS

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _can(role: str, domain: str) -> bool:
    return domain in policy.ROLE_DOMAINS.get(role, set())


def _restricted(role: str, domain: str) -> dict:
    return {"restricted": True, "reason": f"{policy.ROLE_LABELS[role]} role has no access to {policy.DOMAIN_LABELS[domain]}"}


def _flags(c: dict) -> list[str]:
    f = []
    card = c["card"]
    if card["balance"] / card["credit_limit"] > 0.5:
        f.append("High card utilization")
    if c["profile"]["upcoming_needs"]:
        f.append("Upcoming cash need")
    if not c["profile"]["consents"].get("wealth", True):
        f.append("AI wealth access withheld")
    if c["mortgage"] and state.mortgage_privilege(c["mortgage"])["remaining_this_year"] > 0:
        f.append("Prepayment room")
    if any("instruction" in (t.get("memo") or "").lower() for t in c["deposit_transactions"]):
        f.append("Unusual memo")
    return f


@router.get("/clients")
def clients(employee: dict = Depends(current_employee)):
    role = employee["role"]
    if role == "compliance":
        return {"clients": [], "note": "Compliance has no client book. Use Audit and Governance."}
    out = []
    for c in state.CLIENTS.values():
        p = c["profile"]
        row = {"client_id": p["client_id"], "name": p["name"], "segment": p["segment"], "since": p["since"]}
        if _can(role, "profile"):
            row["risk_tolerance"] = p["risk_tolerance"]
        if _can(role, "core"):
            row["deposits_total"] = state.deposits_total(c)
        if _can(role, "cards"):
            row["card_balance"] = c["card"]["balance"]
        if _can(role, "mortgage"):
            row["mortgage_balance"] = c["mortgage"]["balance"] if c["mortgage"] else None
        if _can(role, "wealth"):
            row["wealth_total"] = state.wealth_total(c)
        if role in ("advisor", "supervisor"):
            row["flags"] = _flags(c)
        out.append(row)
    return {"clients": out}


@router.get("/clients/{client_id}")
def client_detail(client_id: str, employee: dict = Depends(current_employee)):
    role = employee["role"]
    if role == "compliance":
        raise HTTPException(403, "Compliance has no client book.")
    c = state.get_client(client_id)
    if not c:
        raise HTTPException(404, "Unknown client")
    p = c["profile"]
    header = {"client_id": p["client_id"], "name": p["name"], "segment": p["segment"], "since": p["since"]}
    out = {"header": header, "ai_consent": p["consents"],
           "ai_domains": policy.allowed_domains_for(role, p)}

    if _can(role, "profile"):
        masked, _ = policy.mask_pii(p)
        out["profile"] = masked
    else:
        out["profile"] = _restricted(role, "profile")

    if _can(role, "core"):
        txs, _ = policy.mask_pii(c["deposit_transactions"][:12])
        out["core"] = {"accounts": policy.mask_pii(c["deposits"])[0], "total": state.deposits_total(c),
                       "cashflow": state.cashflow_by_month(c), "recent_transactions": txs}
    else:
        out["core"] = _restricted(role, "core")

    if _can(role, "cards"):
        card = policy.mask_pii(c["card"])[0]
        card["utilization_pct"] = round(100 * c["card"]["balance"] / c["card"]["credit_limit"], 1)
        out["cards"] = {"card": card, "spending": state.spending_by_category(c)}
    else:
        out["cards"] = _restricted(role, "cards")

    if _can(role, "mortgage"):
        m = c["mortgage"]
        out["mortgage"] = {"mortgage": m, "privilege": state.mortgage_privilege(m) if m else None}
    else:
        out["mortgage"] = _restricted(role, "mortgage")

    if _can(role, "wealth"):
        w = c["wealth"]
        out["wealth"] = {
            "accounts": policy.mask_pii(w["accounts"])[0],
            "holdings": [{**h, "market_value": round(h["units"] * h["price"], 2)} for h in w["holdings"]],
            "total": state.wealth_total(c), "cash": state.wealth_cash(c),
            "performance": [{"month": m, "value": v} for m, v in zip(PERFORMANCE_MONTHS, w["performance"])],
        }
    else:
        out["wealth"] = _restricted(role, "wealth")
    return out
