import { useEffect, useRef, useState } from "react";
import { api, streamCopilot } from "../api";
import { bytes } from "../lib/format";
import Markdown from "../lib/Markdown";
import ActivityFeed from "./ActivityFeed";
import ProposalCard from "./ProposalCard";
import { go } from "../App";

/**
 * The copilot panel. mode="client" (bound to the open client, always the
 * private lane) or mode="research" (no client; external lane by default).
 */
export default function Copilot({ mode, clientId, clientName, suggestions = [], user, full = false }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [lane, setLane] = useState(mode === "client" ? "private" : "public");
  const [lanes, setLanes] = useState(null);
  const [egress, setEgress] = useState(0);
  const bottom = useRef(null);

  useEffect(() => { api.lanes().then(setLanes).catch(() => {}); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);

  const laneInfo = lanes?.[lane];
  const canPropose = ["advisor", "supervisor"].includes(user.role);

  async function send(text, laneOverride) {
    const msg = (text ?? input).trim();
    if (!msg || busy) return;
    const useLane = mode === "client" ? "private" : (laneOverride || lane);
    if (laneOverride) setLane(laneOverride);
    const history = messages.filter((m) => m.role === "user" || (m.role === "assistant" && m.reply)).map((m) => ({ role: m.role, text: m.role === "user" ? m.text : m.reply }));
    setMessages((ms) => [...ms, { role: "user", text: msg }, { role: "assistant", steps: [], proposals: [], active: true, question: msg }]);
    setInput("");
    setBusy(true);

    const patch = (fn) => setMessages((ms) => { const copy = ms.slice(); const last = { ...copy[copy.length - 1] }; fn(last); copy[copy.length - 1] = last; return copy; });
    try {
      await streamCopilot({ mode, client_id: clientId, message: msg, history, lane: useLane }, (ev) => {
        if (ev.type === "final") patch((m) => { m.reply = ev.reply; m.audit_id = ev.audit_id; m.active = false; });
        else if (ev.type === "blocked") patch((m) => { m.blocked = ev; m.audit_id = ev.audit_id; m.active = false; });
        else if (ev.type === "error") patch((m) => { m.error = ev.message; m.active = false; });
        else if (ev.type === "proposal") patch((m) => { m.proposals = [...m.proposals, ev.proposal]; });
        else if (ev.type === "status") { /* spinner only */ }
        else {
          if (ev.type === "start") patch((m) => { m.lane = ev.lane; m.lane_label = ev.lane_label; });
          if (ev.type === "model") { setEgress((e) => e + (ev.egress_bytes || 0)); patch((m) => { m.egress = (m.egress || 0) + (ev.egress_bytes || 0); m.simulated = ev.simulated; }); }
          patch((m) => { m.steps = [...m.steps, ev]; });
        }
      });
    } catch (e) {
      patch((m) => { m.error = e.message; m.active = false; });
    } finally {
      patch((m) => { m.active = false; });
      setBusy(false);
    }
  }

  return (
    <div className={`card copilot ${full ? "full" : ""}`}>
      <div className="cp-head">
        <div className="cp-title">
          ✦ {mode === "client" ? "Advisor Copilot" : "Research Assistant"}
          {mode === "client" && <span className="chip">bound to {clientName}</span>}
          <div className="spacer" />
          {messages.length > 0 && <button className="btn sm" onClick={() => { setMessages([]); setEgress(0); }}>New chat</button>}
        </div>
        {mode === "research" && (
          <div className="row small">
            Model lane:
            <button className={`btn sm ${lane === "public" ? "primary" : ""}`} onClick={() => setLane("public")}>🌐 External</button>
            <button className={`btn sm ${lane === "private" ? "primary" : ""}`} onClick={() => setLane("private")}>🔒 Private</button>
          </div>
        )}
        <div className={`lane ${lane}`}>
          {lane === "private" ? "🔒" : "🌐"}
          <span>
            <b>{lane === "private" ? "Private lane" : "External lane"}</b> · {laneInfo?.label || "…"}
            {laneInfo && <span className="muted"> · {laneInfo.model}</span>}
          </span>
          <div className="spacer" />
          <span>Egress <b>{bytes(egress)}</b></span>
        </div>
        {laneInfo && !laneInfo.configured && <div className="error-box small">No API key set for the {lane} lane on the backend.</div>}
      </div>

      <div className="cp-body">
        {messages.length === 0 && (
          <div className="suggestions">
            <div className="small muted" style={{ marginBottom: 2 }}>
              {mode === "client" ? `Ask about ${clientName}. The copilot can only see what the gateway allows for your role and this client's consent.`
                : lane === "public" ? "External lane: general research only. Client data is blocked before it leaves." : "Private lane: research inside the perimeter."}
            </div>
            {suggestions.map((s) => (
              <button key={s.q} className="suggestion" onClick={() => send(s.q)}>
                {s.tag && <span className="tag">{s.tag}</span>}{s.q}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => m.role === "user" ? (
          <div key={i} className="msg-user">{m.text}</div>
        ) : (
          <div key={i} className="msg-ai">
            <ActivityFeed steps={m.steps} active={m.active} />
            {m.blocked && (
              <div className="blocked">
                <h4>⛔ Blocked by the gateway</h4>
                <div>{m.blocked.reason}</div>
                {m.blocked.hits?.length > 0 && <div className="small" style={{ marginTop: 6 }}>Detected: {m.blocked.hits.join(" · ")}</div>}
                <div className="small muted" style={{ marginTop: 6 }}>Nothing was sent to the external model.</div>
                {m.blocked.can_reroute && <button className="btn sm primary" style={{ marginTop: 10 }} onClick={() => send(m.question, "private")}>Re-run on the private lane</button>}
              </div>
            )}
            {m.error && <div className="error-box">⚠️ {m.error}</div>}
            {m.reply && <Markdown text={m.reply} />}
            {m.proposals.map((p) => <ProposalCard key={p.id} proposal={p} canSend={canPropose} />)}
            {!m.active && m.audit_id && (
              <div className="msg-foot">
                <span>{m.lane === "private" ? "🔒 Private lane" : "🌐 External lane"} · egress {bytes(m.egress || 0)}{m.lane === "private" && m.simulated ? " (simulated)" : ""}</span>
                <div className="spacer" />
                <a href="#" onClick={(e) => { e.preventDefault(); go(`audit/${m.audit_id}`); }}>Audit {m.audit_id}</a>
              </div>
            )}
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <div className="cp-input">
        <textarea value={input} placeholder={mode === "client" ? `Ask about ${clientName}…` : "Ask a research question…"}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
        <button className="btn primary" disabled={busy || !input.trim()} onClick={() => send()}>{busy ? "…" : "Send"}</button>
      </div>
    </div>
  );
}
