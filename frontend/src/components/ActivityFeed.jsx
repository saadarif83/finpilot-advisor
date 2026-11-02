import { useState } from "react";
import { prettyTool, DECISION_PILL, bytes } from "../lib/format";

// The live "what the copilot did" trace for one answer: lane routing,
// which tools the gateway offered/hid, every tool call and the gateway's
// decision for it. This is what makes the architecture visible on stage.
export default function ActivityFeed({ steps, active }) {
  const [open, setOpen] = useState(true);
  const [showHidden, setShowHidden] = useState(false);
  if (!steps.length && !active) return null;
  const calls = steps.filter((s) => s.type === "gateway").length;

  return (
    <div className="feed">
      <div className="feed-head" onClick={() => setOpen(!open)}>
        <span>{open ? "▾" : "▸"}</span>
        {active ? "Working through the gateway…" : `Gateway trace · ${calls} tool call${calls === 1 ? "" : "s"}`}
      </div>
      {open && (
        <div className="feed-steps">
          {steps.map((s, i) => {
            if (s.type === "start") return (
              <div key={i} className="step"><span className="ico">{s.lane === "private" ? "🔒" : "🌐"}</span>
                <span>Routed to <b>{s.lane === "private" ? "private lane" : "external lane"}</b> <span className="detail">· {s.lane_label} · {s.model}</span></span></div>);
            if (s.type === "tools") return (
              <div key={i}>
                <div className="step"><span className="ico">🧰</span>
                  <span>Gateway offered <b>{s.offered}</b> tools{s.hidden.length ? <> · <a href="#" onClick={(e) => { e.preventDefault(); setShowHidden(!showHidden); }}>{s.hidden.length} hidden</a></> : null}</span></div>
                {showHidden && <div className="hidden-list">{s.hidden.map((h) => <div key={h.tool}><span className="tool">{h.tool}</span> — {h.reason}</div>)}</div>}
              </div>);
            if (s.type === "tool_call") return (
              <div key={i} className="step"><span className="ico">→</span><span>Model requested <span className="tool">{prettyTool(s.tool)}</span>{Object.keys(s.input || {}).length ? <span className="detail"> {JSON.stringify(s.input)}</span> : null}</span></div>);
            if (s.type === "gateway") {
              const [label, cls] = DECISION_PILL[s.decision] || [s.decision, "neutral"];
              return (
                <div key={i} className="step"><span className="ico">🛡️</span>
                  <span><span className={`pill ${cls}`}>{label}</span> <span className="detail">{s.detail}</span>
                    {s.flags?.length ? <div className="memo suspicious">“{s.flags[0].excerpt}”</div> : null}</span></div>);
            }
            if (s.type === "model") return (
              <div key={i} className="step"><span className="ico">✦</span><span className="detail">
                Model call · {bytes(s.bytes_out)} sent · {s.egress_bytes ? <b style={{ color: "var(--warn)" }}>{bytes(s.egress_bytes)} egress</b> : <>0 B egress{s.simulated ? " (simulated in-perimeter)" : ""}</>}</span></div>);
            return null;
          })}
          {active && <div className="step"><span className="ico">⏳</span><span className="detail">…</span></div>}
        </div>
      )}
    </div>
  );
}
