"""
THE POLICY — everything the gateway enforces, in one readable place.

This is deliberately plain data, so it can be shown on screen (Governance
console) and explained to a security reviewer line by line. In production
this would live in a policy engine (e.g. OPA/Rego) and be versioned.
"""
import re

POLICY_VERSION = "2026.11-demo"

# --------------------------------------------------------------- tool registry
# Only tools listed here are ever shown to a model, even if an MCP server
# exposes more. "Approved tool registry" = a new tool needs a policy change.
#   domain       which back-end system / data domain it touches
#   kind         read | propose   (nothing can "execute" — see proposals/executor.py)
#   client_data  True if it returns a specific client's data
#   uses         for propose tools: the domains whose data it reads
TOOL_REGISTRY = {
    "core.get_deposit_accounts":   {"domain": "core", "kind": "read", "client_data": True},
    "core.get_transactions":       {"domain": "core", "kind": "read", "client_data": True},
    "core.get_cashflow":           {"domain": "core", "kind": "read", "client_data": True},
    "cards.get_card_account":      {"domain": "cards", "kind": "read", "client_data": True},
    "cards.get_card_transactions": {"domain": "cards", "kind": "read", "client_data": True},
    "cards.get_spending_breakdown": {"domain": "cards", "kind": "read", "client_data": True},
    "mortgage.get_mortgage":       {"domain": "mortgage", "kind": "read", "client_data": True},
    "wealth.get_holdings":         {"domain": "wealth", "kind": "read", "client_data": True},
    "wealth.get_wealth_cash":      {"domain": "wealth", "kind": "read", "client_data": True},
    "wealth.get_performance":      {"domain": "wealth", "kind": "read", "client_data": True},
    "profile.get_client_profile":  {"domain": "profile", "kind": "read", "client_data": True},
    "research.get_market_news":    {"domain": "research", "kind": "read", "client_data": False},
    "research.get_product_rates":  {"domain": "research", "kind": "read", "client_data": False},
    "research.search_policies":    {"domain": "research", "kind": "read", "client_data": False},
    "advice.propose_card_payoff":         {"domain": "advice", "kind": "propose", "client_data": True, "uses": ["cards", "core", "profile"]},
    "advice.propose_mortgage_prepayment": {"domain": "advice", "kind": "propose", "client_data": True, "uses": ["mortgage", "core", "profile"]},
    "advice.propose_gic_purchase":        {"domain": "advice", "kind": "propose", "client_data": True, "uses": ["core", "profile"]},
}

DOMAIN_LABELS = {
    "core": "Core banking (deposits)",
    "cards": "Card platform",
    "mortgage": "Mortgage servicing",
    "wealth": "Wealth platform",
    "profile": "Client profile / KYC",
    "research": "Research (no client data)",
    "advice": "Advice planning (proposals)",
}

# --------------------------------------------------------------- role access
ROLE_DOMAINS = {
    "advisor":    {"core", "cards", "mortgage", "wealth", "profile", "research", "advice"},
    "supervisor": {"core", "cards", "mortgage", "wealth", "profile", "research", "advice"},
    "teller":     {"core", "cards", "research"},
    "compliance": {"research"},
}
ROLE_LABELS = {"advisor": "Advisor", "supervisor": "Supervisor", "teller": "Teller", "compliance": "Compliance"}

# Domains that also require the CLIENT's consent flag (client profile -> consents).
CONSENT_GATED_DOMAINS = {"wealth"}

# --------------------------------------------------------------- lanes
# Which kinds of tools each model lane may use.
#   private = inside the perimeter: client data allowed
#   public  = external model API: no client data, ever
LANE_RULES = {
    "private": {"client_data_allowed": True},
    "public": {"client_data_allowed": False},
}


def role_allows(role: str, tool_key: str) -> tuple[bool, str]:
    meta = TOOL_REGISTRY.get(tool_key)
    if not meta:
        return False, "Tool is not in the approved tool registry"
    if meta["domain"] not in ROLE_DOMAINS.get(role, set()):
        return False, f"Role '{ROLE_LABELS.get(role, role)}' has no access to {DOMAIN_LABELS[meta['domain']]}"
    if meta["kind"] == "propose" and role not in ("advisor", "supervisor"):
        return False, "Only advisors and supervisors may prepare proposals"
    for d in meta.get("uses", []):
        if d not in ROLE_DOMAINS.get(role, set()):
            return False, f"Proposal needs {DOMAIN_LABELS[d]}, which this role cannot access"
    return True, "Allowed by role policy"


def consent_allows(client_profile: dict | None, tool_key: str) -> tuple[bool, str]:
    meta = TOOL_REGISTRY[tool_key]
    if not meta["client_data"] or client_profile is None:
        return True, ""
    consents = client_profile.get("consents", {})
    if not consents.get("ai_assist", False):
        return False, "Client has not consented to AI-assisted advice"
    if meta["domain"] in CONSENT_GATED_DOMAINS and not consents.get(meta["domain"], False):
        return False, f"Client has not consented to sharing {DOMAIN_LABELS[meta['domain']]} data with AI tools"
    return True, ""


def allowed_domains_for(role: str, client_profile: dict | None) -> list[str]:
    """Domains this employee may touch for this client (role AND consent)."""
    out = []
    consents = (client_profile or {}).get("consents", {})
    for d in sorted(ROLE_DOMAINS.get(role, set())):
        if d in CONSENT_GATED_DOMAINS and client_profile is not None and not consents.get(d, False):
            continue
        out.append(d)
    return out


# --------------------------------------------------------------- PII masking
# Fields the gateway masks in every tool result before a model sees them.
# The model never needs a SIN or a full account number to give advice.

def _last(s: str, n: int) -> str:
    digits = re.sub(r"\D", "", s)
    return digits[-n:] if digits else s[-n:]


MASKERS = {
    "sin": lambda v: "***-***-" + _last(v, 3),
    "account_number": lambda v: "••••" + _last(v, 4),
    "card_number": lambda v: "•••• " + _last(v, 4),
    "email": lambda v: (v[0] + "•••@" + v.split("@")[-1]) if "@" in v else "•••",
    "phone": lambda v: "•••-•••-" + _last(v, 4),
    "date_of_birth": lambda v: v[:4] + "-••-••",
    "address": lambda v: "•••, " + ", ".join(v.split(", ")[1:]) if ", " in v else "•••",
}


def mask_pii(obj, path: str = "", masked: list | None = None):
    """Return (masked_copy, list_of_masked_field_paths)."""
    if masked is None:
        masked = []
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k in MASKERS and isinstance(v, str):
                out[k] = MASKERS[k](v)
                masked.append(p)
            else:
                out[k], _ = mask_pii(v, p, masked)
        return out, masked
    if isinstance(obj, list):
        return [mask_pii(v, f"{path}[{i}]", masked)[0] for i, v in enumerate(obj)], masked
    return obj, masked


# --------------------------------------------------------------- injection scan
INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"system (note|prompt|message) to (the )?ai",
    r"you are now",
    r"do not (tell|mention|inform)",
    r"immediately transfer",
    r"pre-?authori[sz]ed",
]
_INJ = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def scan_for_injection(obj, path: str = "", hits: list | None = None) -> list:
    """Find free-text fields that look like instructions aimed at an AI."""
    if hits is None:
        hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            scan_for_injection(v, f"{path}.{k}" if path else k, hits)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            scan_for_injection(v, f"{path}[{i}]", hits)
    elif isinstance(obj, str) and _INJ.search(obj):
        hits.append({"field": path, "excerpt": obj[:140] + ("…" if len(obj) > 140 else "")})
    return hits


def policy_summary() -> dict:
    """For the Governance console."""
    return {
        "version": POLICY_VERSION,
        "domains": DOMAIN_LABELS,
        "roles": {r: sorted(ds) for r, ds in ROLE_DOMAINS.items()},
        "role_labels": ROLE_LABELS,
        "consent_gated_domains": sorted(CONSENT_GATED_DOMAINS),
        "masked_fields": sorted(MASKERS.keys()),
        "lanes": LANE_RULES,
        "tool_registry": TOOL_REGISTRY,
        "rules": [
            "Every model and tool call goes through the gateway — MCP servers reject anything without a gateway pass.",
            "The gateway binds every tool call to the client open on screen; the model cannot choose a different client.",
            "Tools are filtered by role before the model sees them; anything not in the approved registry is never exposed.",
            "Wealth data requires the client's consent for AI use.",
            "SIN, account numbers, card numbers, email, phone, birth date and address are masked before the model sees them.",
            "Free-text fields are scanned for instructions aimed at the AI; hits are flagged and passed as untrusted data.",
            "Client data may only go to the private (in-perimeter) model lane. The external lane is for general research only.",
            "Models can read and propose. Only humans can approve; only the deterministic executor can move money.",
            "Proposals need the client's approval; amounts above the threshold also need a supervisor co-sign.",
            "Every copilot request produces an audit record.",
        ],
    }
