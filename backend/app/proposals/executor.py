"""
THE DETERMINISTIC EXECUTOR — the only code that can move money.

No model and no MCP tool can reach this. It runs only when the approvals
service has collected every required human approval, and it re-checks
everything itself before acting:
  - each approval signature is valid and signs THIS proposal's args hash
  - the parameters still hash to what was approved (tamper check)
  - the required approvers are present (client; supervisor above threshold)
  - the proposal has not already executed (idempotency)
Then it performs the two ledger writes. If the second write fails, it
compensates the first, so accounts never end up half-moved.
"""
from app import state, audit
from app.data_seed import PRODUCTS, DEMO_DATE
from app.proposals import store


class ExecutionRefused(Exception):
    pass


def _verify(p: dict):
    if store.args_hash(p["type"], p["params"]) != p["args_hash"]:
        raise ExecutionRefused("Parameters no longer match what was approved (hash mismatch)")
    roles = set()
    for a in p["approvals"]:
        if a["decision"] != "approved":
            raise ExecutionRefused(f"{a['role']} declined")
        if not store.verify_signature(p, a):
            raise ExecutionRefused(f"Invalid approval signature from {a['by']}")
        roles.add(a["role"])
    if "client" not in roles:
        raise ExecutionRefused("Missing client approval")
    if p["needs_cosign"] and "supervisor" not in roles:
        raise ExecutionRefused("Missing supervisor co-sign")


def execute(p: dict) -> dict:
    if p["status"] == "executed":
        return p["execution"]  # idempotent: never run twice
    _verify(p)
    prm = p["params"]
    cid, amount, src = prm["client_id"], float(prm["amount"]), prm["source_account_id"]

    leg1 = state.ledger_debit_source(cid, src, amount)
    try:
        if p["type"] == "card_payoff":
            leg2 = state.ledger_card_payment(cid, amount)
        elif p["type"] == "mortgage_prepayment":
            leg2 = state.ledger_mortgage_prepayment(cid, amount)
        elif p["type"] == "gic_purchase":
            product = next(g for g in PRODUCTS["gics"] if g["product_id"] == prm["product_id"])
            leg2 = state.ledger_open_gic(cid, product, amount, DEMO_DATE)
        else:
            raise ValueError(f"Unknown proposal type {p['type']}")
    except Exception as e:
        state.ledger_credit_source(cid, src, amount)  # compensate leg 1
        result = {"ok": False, "error": str(e), "compensated": True}
        p["status"], p["execution"] = "failed", result
        store.add_history(p, "failed", "Executor", f"{e} — source refunded")
        audit.add_proposal_event(p["audit_id"], {"proposal_id": p["id"], "event": "execution_failed", "detail": str(e)})
        return result

    result = {"ok": True, "debit": leg1, "credit": leg2}
    p["status"], p["execution"] = "executed", result
    store.add_history(p, "executed", "Executor", "Both ledger writes completed")
    audit.add_proposal_event(p["audit_id"], {"proposal_id": p["id"], "event": "executed", "detail": result})
    return result
