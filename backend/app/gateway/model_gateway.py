"""
THE MODEL GATEWAY — every LLM call goes through here.

Two lanes:
  private  "inside the perimeter". Client data allowed. Counted as 0 bytes of
           data egress.  >>> IN THIS DEMO IT IS SIMULATED <<< by a Claude API
           key. In production, point it at an on-prem model server (vLLM,
           Ollama, Red Hat OpenShift AI, NVIDIA NIM — all speak the OpenAI API)
           by setting PRIVATE_LANE_PROVIDER=openai + BASE_URL + MODEL. No code change.
  public   an external model API. General research only. Every byte sent is
           counted as egress, and a DATA GUARD blocks any request that
           contains client identifiers before it leaves.

The routing decision is made HERE, deterministically, by code — never by a model.
"""
import json
import re
import uuid
import httpx
import anthropic

from app.config import settings
from app import state
from app.gateway import events


class LaneBlocked(Exception):
    def __init__(self, reason: str, hits: list[str]):
        super().__init__(reason)
        self.reason = reason
        self.hits = hits


class ModelError(Exception):
    pass


def lane_config(lane: str) -> dict:
    p = "PRIVATE" if lane == "private" else "PUBLIC"
    return {
        "lane": lane,
        "provider": getattr(settings, f"{p}_LANE_PROVIDER"),
        "api_key": getattr(settings, f"{p}_LANE_API_KEY"),
        "base_url": getattr(settings, f"{p}_LANE_BASE_URL"),
        "model": getattr(settings, f"{p}_LANE_MODEL"),
        "label": getattr(settings, f"{p}_LANE_LABEL"),
        "counts_as_egress": lane == "public",
        "simulated": lane == "private" and getattr(settings, f"{p}_LANE_PROVIDER") == "anthropic",
    }


def public_lane_info() -> dict:
    out = {}
    for lane in ("private", "public"):
        c = lane_config(lane)
        out[lane] = {k: c[k] for k in ("lane", "provider", "model", "label", "counts_as_egress", "simulated")}
        out[lane]["configured"] = bool(c["api_key"]) or c["provider"] == "mock"
    return out


# ------------------------------------------------------------------ routing

def choose_lane(mode: str, requested: str | None, employee: dict, request_id: str) -> str:
    if mode == "client":
        if requested == "public":
            events.record("lane", "routed", employee=employee, lane="private", request_id=request_id,
                          detail="Client context present → forced to private lane (external lane not permitted)")
        else:
            events.record("lane", "routed", employee=employee, lane="private", request_id=request_id,
                          detail="Client context present → private lane (inside perimeter)")
        return "private"
    lane = requested if requested in ("private", "public") else "public"
    events.record("lane", "routed", employee=employee, lane=lane, request_id=request_id,
                  detail="No client context → " + ("external lane allowed" if lane == "public" else "private lane by request"))
    return lane


# ------------------------------------------------------------------ data guard

def _identifier_index() -> list[tuple[str, str]]:
    """Every client identifier the bank knows about, for the egress data guard."""
    idx = []
    for c in state.CLIENTS.values():
        p = c["profile"]
        idx.append(("client name", p["name"]))
        surname = p["name"].split()[-1]
        idx.append(("client surname", surname))
        idx.append(("SIN", p["sin"]))
        idx.append(("email", p["email"]))
        idx.append(("phone", p["phone"]))
        for a in c["deposits"]:
            idx.append(("account number", a["account_number"]))
        idx.append(("card number", c["card"]["card_number"]))
        for a in c["wealth"]["accounts"]:
            idx.append(("account number", a["account_number"]))
        idx.append(("client id", p["client_id"]))
    return idx


_GENERIC = [
    ("SIN-like number", re.compile(r"\b\d{3}[- ]\d{3}[- ]\d{3}\b")),
    ("card-like number", re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b")),
]


def data_guard(payload_text: str) -> list[str]:
    hits = []
    low = payload_text.lower()
    for kind, value in _identifier_index():
        if value and value.lower() in low:
            hits.append(f"{kind}: {value}")
    for kind, rx in _GENERIC:
        m = rx.search(payload_text)
        if m:
            hits.append(f"{kind}: {m.group(0)}")
    # de-duplicate, keep order
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


# ------------------------------------------------------------------ providers

async def _call_anthropic(cfg: dict, system: str, messages: list, tools: list, max_tokens: int) -> dict:
    if not cfg["api_key"]:
        raise ModelError(f"No API key configured for the {cfg['lane']} lane ({cfg['lane'].upper()}_LANE_API_KEY).")
    client = anthropic.AsyncAnthropic(api_key=cfg["api_key"], base_url=cfg["base_url"] or None)
    kwargs = {"model": cfg["model"], "max_tokens": max_tokens, "system": system, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    resp = await client.messages.create(**kwargs)
    blocks = []
    for b in resp.content:
        if b.type == "text":
            blocks.append({"type": "text", "text": b.text})
        elif b.type == "tool_use":
            blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return {"stop_reason": resp.stop_reason, "content": blocks, "model": resp.model}


def _to_openai_messages(system: str, messages: list) -> list:
    out = [{"role": "system", "content": system}]
    for m in messages:
        if isinstance(m["content"], str):
            out.append({"role": m["role"], "content": m["content"]})
            continue
        if m["role"] == "assistant":
            text = "".join(b["text"] for b in m["content"] if b["type"] == "text")
            calls = [{"id": b["id"], "type": "function", "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
                     for b in m["content"] if b["type"] == "tool_use"]
            msg = {"role": "assistant", "content": text or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
        else:
            for b in m["content"]:
                if b["type"] == "tool_result":
                    out.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"]})
                elif b["type"] == "text":
                    out.append({"role": "user", "content": b["text"]})
    return out


async def _call_openai_compatible(cfg: dict, system: str, messages: list, tools: list, max_tokens: int) -> dict:
    """For on-prem servers (vLLM, Ollama, OpenShift AI, NIM...) that speak the OpenAI chat API."""
    if not cfg["base_url"]:
        raise ModelError(f"{cfg['lane']} lane provider is 'openai' but no BASE_URL is set.")
    body = {"model": cfg["model"], "max_tokens": max_tokens, "messages": _to_openai_messages(system, messages)}
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                            "parameters": t["input_schema"]}} for t in tools]
    headers = {"Authorization": f"Bearer {cfg['api_key']}"} if cfg["api_key"] else {}
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{cfg['base_url']}/chat/completions", json=body, headers=headers)
    if r.status_code != 200:
        raise ModelError(f"Model server returned {r.status_code}: {r.text[:300]}")
    choice = r.json()["choices"][0]
    msg = choice["message"]
    blocks = []
    if msg.get("content"):
        blocks.append({"type": "text", "text": msg["content"]})
    for tc in msg.get("tool_calls") or []:
        try:
            args = json.loads(tc["function"].get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        blocks.append({"type": "tool_use", "id": tc.get("id") or "call_" + uuid.uuid4().hex[:8], "name": tc["function"]["name"], "input": args})
    stop = "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn"
    return {"stop_reason": stop, "content": blocks, "model": cfg["model"]}


async def _call_mock(cfg: dict, system: str, messages: list, tools: list, max_tokens: int) -> dict:
    """TESTING ONLY: a scripted stand-in model so the whole flow can be tested without an API key."""
    from app.gateway.mock_model import respond
    return respond(messages, tools)


PROVIDERS = {"anthropic": _call_anthropic, "openai": _call_openai_compatible, "mock": _call_mock}


# ------------------------------------------------------------------ the call

async def complete(*, lane: str, system: str, messages: list, tools: list, employee: dict,
                   request_id: str, client_id: str | None, max_tokens: int = 1500) -> dict:
    cfg = lane_config(lane)
    if events.kill_switch_enabled():
        events.record("model", "blocked", employee=employee, lane=lane, client_id=client_id, request_id=request_id,
                      detail="Kill switch is ON — model calls suspended")
        raise LaneBlocked("Kill switch is ON — all AI activity is suspended.", [])

    payload = json.dumps({"system": system, "messages": messages, "tools": tools}, default=str)
    if lane == "public":
        # Tool definitions are the bank's own text; only scan what could carry client data.
        hits = data_guard(json.dumps({"messages": messages}, default=str))
        if hits:
            events.lane_add("public", blocked=True)
            events.record("model", "blocked", employee=employee, lane=lane, client_id=client_id, request_id=request_id,
                          detail="DATA GUARD: client data detected in a request bound for the external lane — blocked before leaving. Found " + "; ".join(hits[:4]))
            raise LaneBlocked("Client data detected — the external model lane is not permitted for client information.", hits)

    provider = PROVIDERS.get(cfg["provider"])
    if not provider:
        raise ModelError(f"Unknown provider '{cfg['provider']}' for {lane} lane")
    try:
        result = await provider(cfg, system, messages, tools, max_tokens)
    except anthropic.APIError as e:
        raise ModelError(f"Model API error ({lane} lane): {e}") from e
    except httpx.HTTPError as e:
        raise ModelError(f"Model server unreachable ({lane} lane): {e}") from e

    bytes_out = len(payload.encode())
    bytes_in = len(json.dumps(result["content"], default=str).encode())
    events.lane_add(lane, bytes_out=bytes_out, bytes_in=bytes_in)
    egress_note = (f"{bytes_out:,} B left the perimeter" if cfg["counts_as_egress"]
                   else "0 B egress (inside perimeter" + (" — simulated)" if cfg["simulated"] else ")"))
    events.record("model", "routed", employee=employee, lane=lane, client_id=client_id, request_id=request_id,
                  detail=f"{cfg['label']} · {cfg['model']} · {egress_note}",
                  extra={"bytes_out": bytes_out, "bytes_in": bytes_in})
    result.update({"lane": lane, "label": cfg["label"], "bytes_out": bytes_out, "bytes_in": bytes_in,
                   "egress_bytes": bytes_out if cfg["counts_as_egress"] else 0, "simulated": cfg["simulated"]})
    return result
