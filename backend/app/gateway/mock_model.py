"""
TESTING ONLY — a scripted stand-in for a real model.

Set PRIVATE_LANE_PROVIDER=mock / PUBLIC_LANE_PROVIDER=mock to exercise the
whole app (gateway, tools, proposals, approvals, audit) without an API key.
It picks tools by keyword and then writes a plain summary. Never use on stage.
"""
import json
import uuid

PLANS = [
    (("card", "pay down", "payoff", "debt"), ["profile__get_client_profile", "cards__get_card_account", "core__get_deposit_accounts", "wealth__get_wealth_cash", "advice__propose_card_payoff"]),
    (("mortgage", "prepay"), ["profile__get_client_profile", "mortgage__get_mortgage", "core__get_deposit_accounts", "advice__propose_mortgage_prepayment"]),
    (("gic", "idle", "savings"), ["profile__get_client_profile", "core__get_deposit_accounts", "research__get_product_rates", "advice__propose_gic_purchase"]),
    (("transaction", "activity", "unusual"), ["core__get_transactions"]),
    (("portfolio", "invest", "holding"), ["wealth__get_holdings", "wealth__get_performance"]),
    (("news", "market", "rate"), ["research__get_market_news", "research__get_product_rates"]),
    (("policy",), ["research__search_policies"]),
]
DEFAULT_PLAN = ["profile__get_client_profile", "core__get_deposit_accounts", "cards__get_card_account", "mortgage__get_mortgage"]


def _first_user_text(messages: list) -> str:
    for m in reversed(messages):
        if m["role"] == "user" and isinstance(m["content"], str):
            return m["content"].lower()
    return ""


def respond(messages: list, tools: list) -> dict:
    available = {t["name"] for t in tools}
    question = _first_user_text(messages)
    plan = next((p for keys, p in PLANS if any(k in question for k in keys)), DEFAULT_PLAN)
    plan = [t for t in plan if t in available]

    called = []
    results = []
    for m in messages:
        if m["role"] == "assistant" and isinstance(m["content"], list):
            called += [b["name"] for b in m["content"] if b["type"] == "tool_use"]
        if m["role"] == "user" and isinstance(m["content"], list):
            results += [b["content"] for b in m["content"] if b["type"] == "tool_result"]

    remaining = [t for t in plan if t not in called]
    if remaining:
        args = {"query": question} if remaining[0] == "research__search_policies" else {}
        return {"stop_reason": "tool_use", "model": "mock",
                "content": [{"type": "text", "text": "(mock) Checking the relevant systems…"},
                            {"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:10], "name": remaining[0], "input": args}]}

    lines = ["**(Mock model — testing only)**", ""]
    if not plan:
        lines.append("I don't have access to the data needed for that question with your current role.")
    for r in results:
        try:
            data = json.loads(r)
        except (json.JSONDecodeError, TypeError):
            data = {}
        if data.get("ok") is False:
            lines.append(f"- Access denied: {data.get('reason')}")
        elif "gateway_notices" in json.dumps(data):
            lines.append("- ⚠️ A transaction memo contains instructions aimed at an AI. I ignored them — please refer to Fraud Operations.")
        elif "proposal_id" in json.dumps(data):
            lines.append("- I've prepared a proposal for your review; it needs the client's approval before anything moves.")
    if len(lines) == 2:
        lines.append("- Summary of the data retrieved is available in the activity feed.")
    return {"stop_reason": "end_turn", "model": "mock", "content": [{"type": "text", "text": "\n".join(lines)}]}
