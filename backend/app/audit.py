"""
Audit evidence records — one per copilot request.

This is the artifact a compliance officer or model-risk reviewer asks for:
who asked, about which client, which model and lane, which tools were
called and what the gateway decided for each, what data was masked, what
was flagged, what was proposed, who approved it, and what was executed.
In-memory for the demo; in production, append-only (WORM) storage.
"""
import time
import uuid

_records: dict[str, dict] = {}
_order: list[str] = []


def start(*, employee: dict, client: dict | None, message: str, mode: str) -> dict:
    rid = "A-" + uuid.uuid4().hex[:8].upper()
    rec = {
        "id": rid,
        "started_at": time.time(),
        "finished_at": None,
        "employee": {"username": employee["username"], "name": employee["name"], "role": employee["role"]},
        "client": {"client_id": client["client_id"], "name": client["name"]} if client else None,
        "mode": mode,  # client | research
        "question": message,
        "lane": None,
        "model": None,
        "model_calls": [],
        "tool_calls": [],
        "masked_fields": [],
        "injection_flags": [],
        "data_domains": [],
        "proposals": [],
        "proposal_events": [],
        "outcome": "in_progress",
        "answer": None,
    }
    _records[rid] = rec
    _order.append(rid)
    return rec


def get(rid: str) -> dict | None:
    return _records.get(rid)


def add_tool_call(rid: str, entry: dict):
    rec = _records.get(rid)
    if not rec:
        return
    rec["tool_calls"].append(entry)
    for f in entry.get("masked_fields", []):
        if f not in rec["masked_fields"]:
            rec["masked_fields"].append(f)
    rec["injection_flags"].extend(entry.get("flags", []))
    d = entry.get("domain")
    if d and entry.get("decision") != "denied" and d not in rec["data_domains"]:
        rec["data_domains"].append(d)


def add_model_call(rid: str, entry: dict):
    rec = _records.get(rid)
    if rec:
        rec["model_calls"].append(entry)


def add_proposal(rid: str, proposal_id: str):
    rec = _records.get(rid)
    if rec and proposal_id not in rec["proposals"]:
        rec["proposals"].append(proposal_id)


def add_proposal_event(rid: str | None, event: dict):
    rec = _records.get(rid or "")
    if rec:
        rec["proposal_events"].append({"at": time.time(), **event})


def finish(rid: str, *, outcome: str, answer: str | None = None):
    rec = _records.get(rid)
    if rec:
        rec["finished_at"] = time.time()
        rec["outcome"] = outcome
        rec["answer"] = (answer or "")[:4000]


def list_records(employee: dict) -> list[dict]:
    recs = [_records[r] for r in reversed(_order)]
    if employee["role"] not in ("compliance", "supervisor"):
        recs = [r for r in recs if r["employee"]["username"] == employee["username"]]
    return [
        {k: r[k] for k in ("id", "started_at", "employee", "client", "mode", "question", "lane", "model", "outcome")}
        | {"tool_count": len(r["tool_calls"]), "denied": sum(1 for t in r["tool_calls"] if t["decision"] == "denied"),
           "flags": len(r["injection_flags"]), "proposals": len(r["proposals"])}
        for r in recs
    ]


def reset():
    _records.clear()
    _order.clear()
