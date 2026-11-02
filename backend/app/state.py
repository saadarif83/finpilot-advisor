"""
The live, mutable state of the simulated bank's back-end systems.

Everything is in memory: a backend restart (or the "Reset demo" button)
puts every client back to the seed data in data_seed.py.

In a real bank each of these would be a separate system of record (core
banking, card platform, mortgage servicing, wealth platform, CRM). The
ledger_* functions below play the part of those systems' write APIs; only
the deterministic executor (proposals/executor.py) ever calls them.
"""
import copy
from app import data_seed

CLIENTS: dict = {}


def reset_state():
    CLIENTS.clear()
    CLIENTS.update(copy.deepcopy(data_seed.CLIENTS))


reset_state()


def get_client(client_id: str) -> dict | None:
    return CLIENTS.get(client_id)


def client_ids() -> list[str]:
    return list(CLIENTS.keys())


# ---------------------------------------------------------------- derived views

def deposits_total(c: dict) -> float:
    return round(sum(a["balance"] for a in c["deposits"]), 2)


def wealth_cash(c: dict) -> float:
    return round(sum(a["cash"] for a in c["wealth"]["accounts"]), 2)


def wealth_holdings_value(c: dict) -> float:
    return round(sum(h["units"] * h["price"] for h in c["wealth"]["holdings"]), 2)


def wealth_total(c: dict) -> float:
    return round(wealth_holdings_value(c) + wealth_cash(c), 2)


def find_deposit(c: dict, account_id: str) -> dict | None:
    return next((a for a in c["deposits"] if a["account_id"] == account_id), None)


def find_wealth_account(c: dict, account_id: str) -> dict | None:
    return next((a for a in c["wealth"]["accounts"] if a["account_id"] == account_id), None)


def cashflow_by_month(c: dict) -> list[dict]:
    buckets: dict[str, dict] = {}
    for tx in c["deposit_transactions"]:
        m = tx["date"][:7]
        b = buckets.setdefault(m, {"month": m, "in": 0.0, "out": 0.0})
        if tx["amount"] >= 0:
            b["in"] += tx["amount"]
        else:
            b["out"] += -tx["amount"]
    return [{"month": k, "in": round(v["in"], 2), "out": round(v["out"], 2)} for k, v in sorted(buckets.items())]


def spending_by_category(c: dict) -> list[dict]:
    totals: dict[str, float] = {}
    for tx in c["card_transactions"]:
        if tx["amount"] < 0:
            cat = tx.get("category", "Other")
            totals[cat] = totals.get(cat, 0.0) + (-tx["amount"])
    return sorted(({"category": k, "amount": round(v, 2)} for k, v in totals.items()), key=lambda r: -r["amount"])


def mortgage_privilege(m: dict) -> dict:
    annual = round(m["original_principal"] * m["prepayment_privilege_pct"] / 100, 2)
    remaining = round(max(0.0, annual - m["prepaid_this_year"]), 2)
    return {"annual_privilege": annual, "used_this_year": m["prepaid_this_year"], "remaining_this_year": remaining}


# ---------------------------------------------------------------- ledger writes
# Simulated system-of-record write APIs. Each raises ValueError on failure.

def ledger_debit_source(client_id: str, source_account_id: str, amount: float) -> dict:
    c = CLIENTS[client_id]
    dep = find_deposit(c, source_account_id)
    if dep:
        if dep["balance"] < amount:
            raise ValueError(f"Insufficient funds in {dep['name']}")
        dep["balance"] = round(dep["balance"] - amount, 2)
        return {"account_id": source_account_id, "new_balance": dep["balance"]}
    wa = find_wealth_account(c, source_account_id)
    if wa:
        if wa["cash"] < amount:
            raise ValueError(f"Insufficient cash in {wa['type']} account")
        wa["cash"] = round(wa["cash"] - amount, 2)
        return {"account_id": source_account_id, "new_cash": wa["cash"]}
    raise ValueError(f"Unknown source account {source_account_id}")


def ledger_credit_source(client_id: str, source_account_id: str, amount: float) -> dict:
    """Compensating action: put money back where it came from."""
    c = CLIENTS[client_id]
    dep = find_deposit(c, source_account_id)
    if dep:
        dep["balance"] = round(dep["balance"] + amount, 2)
        return {"account_id": source_account_id, "new_balance": dep["balance"]}
    wa = find_wealth_account(c, source_account_id)
    if wa:
        wa["cash"] = round(wa["cash"] + amount, 2)
        return {"account_id": source_account_id, "new_cash": wa["cash"]}
    raise ValueError(f"Unknown source account {source_account_id}")


def ledger_card_payment(client_id: str, amount: float) -> dict:
    card = CLIENTS[client_id]["card"]
    if amount > card["balance"] + 0.005:
        raise ValueError("Payment exceeds card balance")
    card["balance"] = round(card["balance"] - amount, 2)
    return {"card_id": card["card_id"], "new_balance": card["balance"]}


def ledger_mortgage_prepayment(client_id: str, amount: float) -> dict:
    m = CLIENTS[client_id]["mortgage"]
    if not m:
        raise ValueError("Client has no mortgage")
    if amount > mortgage_privilege(m)["remaining_this_year"] + 0.005:
        raise ValueError("Prepayment exceeds this year's privilege")
    m["balance"] = round(m["balance"] - amount, 2)
    m["prepaid_this_year"] = round(m["prepaid_this_year"] + amount, 2)
    return {"mortgage_id": m["mortgage_id"], "new_balance": m["balance"]}


def ledger_open_gic(client_id: str, product: dict, amount: float, opened_on: str) -> dict:
    c = CLIENTS[client_id]
    n = sum(1 for a in c["deposits"] if a["type"] == "gic") + 1
    acct = {
        "account_id": f"dep-{client_id[2:]}-gic{n}",
        "type": "gic",
        "name": product["name"],
        "account_number": f"00499-{client_id[2:]}-GIC{n}",
        "balance": round(amount, 2),
        "rate": product["rate"],
        "term_months": product["term_months"],
        "opened": opened_on,
    }
    c["deposits"].append(acct)
    return {"account_id": acct["account_id"], "balance": acct["balance"]}
