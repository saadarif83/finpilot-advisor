"""
MCP server for ADVICE PLANNING. Owner: Advice Desk.

These tools only COMPUTE a proposal. None of them can move money: there is no
write API reachable from here. When a proposal comes back through the gateway,
the gateway records it, and from then on only humans (client approval, and a
supervisor co-sign above the threshold) can release it to the deterministic
executor (app/proposals/executor.py).

For the demo this service reads the systems of record from shared memory; in
a real bank it would read them through their own APIs.
"""
from mcp.server.mcpserver import MCPServer, Context
from app.mcp_servers.common import require_gateway_pass, load_client
from app.data_seed import PRODUCTS
from app.config import settings
from app import state

SERVER = "advice"
mcp = MCPServer(name="northstead-advice-planning", instructions="Computes advice proposals with suitability checks. Never executes anything.")


def _buffer(profile: dict) -> tuple[float, int]:
    months = int(profile.get("buffer_months", 3))
    return round(profile["monthly_expenses"] * months, 2), months


def _liquid(c: dict) -> float:
    return round(sum(a["balance"] for a in c["deposits"] if a["type"] in ("chequing", "savings")), 2)


def _hisa(c: dict) -> dict | None:
    return next((a for a in c["deposits"] if a["type"] == "savings"), None)


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _needs_soon(profile: dict, within_months: int = 24) -> float:
    return round(sum(n["amount"] for n in profile.get("upcoming_needs", []) if n["in_months"] <= within_months), 2)


def _cosign_note(amount: float) -> str:
    if amount > settings.COSIGN_THRESHOLD:
        return f"Requires client approval AND a supervisor co-sign (above {_money(settings.COSIGN_THRESHOLD)})."
    return "Requires client approval."


@mcp.tool()
async def propose_card_payoff(client_id: str, ctx: Context) -> dict:
    """Prepare a proposal to pay down the client's credit card from idle cash above their liquidity buffer.
    Considers the high-interest savings account and (if consented) TFSA cash. Computes only — never moves money."""
    claims = require_gateway_pass(ctx, SERVER, "propose_card_payoff", client_id)
    c = load_client(client_id)
    p, card = c["profile"], c["card"]
    buffer, months = _buffer(p)
    checks = []
    if card["balance"] <= 0:
        return {"recommended": False, "reason": "Card has no balance."}
    if card["apr"] < 18:
        return {"recommended": False, "reason": f"Card APR {card['apr']}% is below the 18% policy trigger (POL-ADV-027)."}
    checks.append({"check": "High-interest debt", "result": "pass", "detail": f"Card APR {card['apr']}% exceeds the 18% trigger (POL-ADV-027)."})

    hisa = _hisa(c)
    liquid = _liquid(c)
    candidates = []
    if hisa:
        avail = round(max(0.0, min(hisa["balance"], liquid - buffer)), 2)
        candidates.append({"account_id": hisa["account_id"], "label": hisa["name"], "available": avail, "yield": hisa.get("rate", 0)})
    checks.append({"check": "Liquidity buffer", "result": "pass", "detail": f"Keeps {months} months of expenses ({_money(buffer)}) in chequing + savings."})

    if "wealth" in claims.get("domains", []):
        for a in c["wealth"]["accounts"]:
            if a["type"] == "TFSA" and a["cash"] > 0:
                candidates.append({"account_id": a["account_id"], "label": "TFSA cash", "available": a["cash"], "yield": 0.0})
        checks.append({"check": "Tax treatment", "result": "pass", "detail": "RRSP cash excluded (withdrawals are taxable); TFSA cash eligible."})
    else:
        checks.append({"check": "Consent", "result": "adjusted", "detail": "Wealth accounts not considered — client has not consented to AI use of wealth data."})

    candidates = [x for x in candidates if x["available"] > 0]
    if not candidates:
        return {"recommended": False, "reason": "No idle cash above the client's liquidity buffer.", "checks": checks}
    # Prefer the lowest-yielding source that covers the whole balance; otherwise the largest.
    covering = sorted([x for x in candidates if x["available"] >= card["balance"]], key=lambda x: x["yield"])
    src = covering[0] if covering else max(candidates, key=lambda x: x["available"])
    amount = round(min(card["balance"], src["available"]), 2)
    savings = round(amount * card["apr"] / 100 - amount * src["yield"] / 100, 2)

    return {
        "recommended": True,
        "type": "card_payoff",
        "title": f"Pay {_money(amount)} toward the {card['product']}",
        "params": {"client_id": client_id, "source_account_id": src["account_id"], "card_id": card["card_id"], "amount": amount},
        "summary": {
            "source": src["label"],
            "before": {"card_balance": card["balance"], "source_balance": src["available"] if src["label"] == "TFSA cash" else hisa["balance"]},
            "after": {"card_balance": round(card["balance"] - amount, 2),
                      "source_balance": round((src["available"] if src["label"] == "TFSA cash" else hisa["balance"]) - amount, 2)},
            "estimated_annual_benefit": savings,
        },
        "rationale": (f"The card charges {card['apr']}% while this cash earns {src['yield']}%. Moving {_money(amount)} from "
                      f"{src['label']} saves about {_money(savings)} a year and keeps the {months}-month buffer intact."),
        "checks": checks,
        "approvals_required": _cosign_note(amount),
    }


@mcp.tool()
async def propose_mortgage_prepayment(client_id: str, ctx: Context, amount: float | None = None) -> dict:
    """Prepare a lump-sum mortgage prepayment proposal from savings, capped by this year's prepayment privilege
    and the client's liquidity buffer. Optionally pass a requested amount. Computes only — never moves money."""
    require_gateway_pass(ctx, SERVER, "propose_mortgage_prepayment", client_id)
    c = load_client(client_id)
    p, m = c["profile"], c["mortgage"]
    if not m:
        return {"recommended": False, "reason": "Client has no mortgage with Northstead Financial."}
    buffer, months = _buffer(p)
    hisa = _hisa(c)
    priv = state.mortgage_privilege(m)
    avail_cash = round(max(0.0, min(hisa["balance"], _liquid(c) - buffer - _needs_soon(p))), 2)
    cap = min(priv["remaining_this_year"], avail_cash)
    checks = [
        {"check": "Rate comparison", "result": "pass" if m["rate"] > hisa.get("rate", 0) else "fail",
         "detail": f"Mortgage {m['rate']}% vs savings {hisa.get('rate', 0)}%."},
        {"check": "Prepayment privilege", "result": "pass",
         "detail": f"{_money(priv['remaining_this_year'])} of {_money(priv['annual_privilege'])} left this year (POL-ADV-014)."},
        {"check": "Liquidity buffer", "result": "pass", "detail": f"Keeps {months} months of expenses ({_money(buffer)})."},
    ]
    if cap <= 0:
        return {"recommended": False, "reason": "No prepayment room or no idle cash above the buffer.", "checks": checks}
    target = cap if amount is None else min(float(amount), cap)
    if amount is not None and float(amount) > cap:
        checks.append({"check": "Requested amount", "result": "adjusted",
                       "detail": f"Requested {_money(float(amount))} reduced to {_money(cap)} to stay within privilege and buffer."})
    target = round(target, 2)
    year1 = round(target * (m["rate"] - hisa.get("rate", 0)) / 100, 2)
    return {
        "recommended": True,
        "type": "mortgage_prepayment",
        "title": f"Prepay {_money(target)} on the mortgage",
        "params": {"client_id": client_id, "source_account_id": hisa["account_id"], "mortgage_id": m["mortgage_id"], "amount": target},
        "summary": {
            "source": hisa["name"],
            "before": {"mortgage_balance": m["balance"], "source_balance": hisa["balance"]},
            "after": {"mortgage_balance": round(m["balance"] - target, 2), "source_balance": round(hisa["balance"] - target, 2)},
            "estimated_annual_benefit": year1,
        },
        "rationale": (f"Prepaying {_money(target)} at {m['rate']}% instead of earning {hisa.get('rate', 0)}% in savings is worth about "
                      f"{_money(year1)} in the first year, and more over the remaining {m['amortization_years_remaining']} years."),
        "checks": checks,
        "approvals_required": _cosign_note(target),
    }


@mcp.tool()
async def propose_gic_purchase(client_id: str, ctx: Context, amount: float | None = None, term_months: int | None = None) -> dict:
    """Prepare a proposal to move idle savings into a GIC, with suitability checks (liquidity buffer, upcoming needs,
    time horizon). Optionally pass a requested amount and term in months. Computes only — never moves money."""
    require_gateway_pass(ctx, SERVER, "propose_gic_purchase", client_id)
    c = load_client(client_id)
    p = c["profile"]
    buffer, months = _buffer(p)
    hisa = _hisa(c)
    needs = _needs_soon(p)
    avail = round(max(0.0, min(hisa["balance"], _liquid(c) - buffer - needs)), 2)
    checks = [{"check": "Liquidity buffer", "result": "pass", "detail": f"Keeps {months} months of expenses ({_money(buffer)}) liquid."}]
    if needs:
        need_txt = "; ".join(f"{n['need']} {_money(n['amount'])} in ~{n['in_months']} months" for n in p["upcoming_needs"])
        checks.append({"check": "Upcoming needs", "result": "pass", "detail": f"Reserved and kept liquid: {need_txt} (POL-ADV-021)."})
    if avail < 1000:
        return {"recommended": False, "reason": "Not enough idle savings above the buffer and upcoming needs.", "checks": checks}

    gics = PRODUCTS["gics"]
    if term_months:
        product = min(gics, key=lambda g: (abs(g["term_months"] - int(term_months)), -g["rate"]))
    else:
        horizon_ok = [g for g in gics if g["term_months"] <= 24 and not g["cashable"]]
        product = max(horizon_ok, key=lambda g: g["rate"])
    checks.append({"check": "Product fit", "result": "pass",
                   "detail": f"{product['name']} at {product['rate']}% suits a {p['risk_tolerance'].lower()} profile with a {p['time_horizon']} horizon."})

    target = float(amount) if amount is not None else (avail // 1000) * 1000
    if target > avail:
        checks.append({"check": "Requested amount", "result": "adjusted",
                       "detail": f"Requested {_money(target)} reduced to {_money(avail)} so the buffer and upcoming needs stay liquid."})
        target = avail
    target = round(target, 2)
    gain = round(target * (product["rate"] - hisa.get("rate", 0)) / 100, 2)
    return {
        "recommended": True,
        "type": "gic_purchase",
        "title": f"Move {_money(target)} into a {product['name']}",
        "params": {"client_id": client_id, "source_account_id": hisa["account_id"], "product_id": product["product_id"], "amount": target},
        "summary": {
            "source": hisa["name"],
            "product": product,
            "before": {"source_balance": hisa["balance"]},
            "after": {"source_balance": round(hisa["balance"] - target, 2), "gic_balance": target},
            "estimated_annual_benefit": gain,
        },
        "rationale": (f"Idle savings earn {hisa.get('rate', 0)}%. Locking {_money(target)} at {product['rate']}% earns about "
                      f"{_money(gain)} more per year, while the buffer and known upcoming needs stay in savings."),
        "checks": checks,
        "approvals_required": _cosign_note(target),
    }
