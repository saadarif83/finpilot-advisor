import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { bytes, time, DECISION_PILL } from "../lib/format";

const KIND_LABEL = { tool: "Tool", model: "Model", lane: "Lane", admin: "Approvals", bypass: "Direct access" };

export default function Governance({ user }) {
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState(null);
  const [policy, setPolicy] = useState(null);
  const [laneInfo, setLaneInfo] = useState(null);
  const [bypass, setBypass] = useState(null);
  const [filter, setFilter] = useState("all");
  const [newIds, setNewIds] = useState(new Set());
  const last = useRef(0);

  useEffect(() => {
    api.policy().then(setPolicy).catch(() => {});
    api.lanes().then(setLaneInfo).catch(() => {});
    let alive = true;
    const tick = async () => {
      try {
        const [ev, st] = await Promise.all([api.events(last.current), api.stats()]);
        if (!alive) return;
        if (ev.events.length) {
          last.current = ev.events[ev.events.length - 1].id;
          setNewIds(new Set(ev.events.map((e) => e.id)));
          setEvents((old) => [...ev.events.slice().reverse(), ...old].slice(0, 600));
        }
        setStats(st);
      } catch { /* keep polling */ }
    };
    tick();
    const id = setInterval(tick, 1500);
    return () => { alive = false; clearInterval(id); };
  }, []);

  const c = stats?.counters || {};
  const lanes = stats?.lanes;
  const kill = stats?.kill_switch?.enabled;
  const shown = events.filter((e) => filter === "all" ? true : filter === "denied" ? ["denied", "blocked"].includes(e.decision) : filter === "flagged" ? e.decision === "flagged" : e.kind === filter);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Governance console</h1>
          <p>Every decision the WWT MCP gateway makes, live. Policy {policy?.version}.</p>
        </div>
      </div>

      <div className="stats">
        <div className="card card-pad stat">
          <div className="card-title">🔒 Private lane · data egress</div>
          <div className="big">0 B</div>
          <div className="small muted">{lanes ? `${lanes.private.calls} model calls · ${bytes(lanes.private.bytes_out)} processed inside the perimeter` : "…"}{laneInfo?.private?.simulated && <><br />Simulated by a Claude API key in this demo</>}</div>
        </div>
        <div className="card card-pad stat">
          <div className="card-title">🌐 External lane · data egress</div>
          <div className="big" style={{ color: lanes?.public.bytes_out ? "var(--warn)" : undefined }}>{lanes ? bytes(lanes.public.bytes_out) : "…"}</div>
          <div className="small muted">{lanes ? `${lanes.public.calls} calls · no client data · ${lanes.public.blocked} blocked by data guard` : ""}</div>
        </div>
        <div className="card card-pad stat">
          <div className="card-title">Tool decisions</div>
          <div className="row" style={{ flexWrap: "wrap", marginTop: 6 }}>
            <span className="pill good">{c.allowed || 0} allowed</span>
            <span className="pill info">{c.masked || 0} masked</span>
            <span className="pill bad">{(c.denied || 0) + (c.blocked || 0)} denied / blocked</span>
            <span className="pill flag">{c.flagged || 0} flagged</span>
          </div>
        </div>
        <div className="card card-pad stat">
          <div className="card-title">Kill switch</div>
          <div className="switch">
            <button className={`toggle ${kill ? "on" : ""}`} aria-label="Kill switch" onClick={() => api.killSwitch(!kill).then(() => api.stats().then(setStats))} />
            <div><b>{kill ? "ON — all AI suspended" : "Off"}</b><div className="small muted">Stops every model and tool call instantly</div></div>
          </div>
        </div>
      </div>

      <div className="gov">
        <div className="card">
          <div className="card-pad row" style={{ paddingBottom: 8 }}>
            <div className="card-title" style={{ margin: 0 }}>Live gateway decisions</div>
            <div className="spacer" />
            {[["all", "All"], ["tool", "Tools"], ["model", "Models"], ["denied", "Denied"], ["flagged", "Flagged"]].map(([k, l]) => (
              <button key={k} className={`btn sm ${filter === k ? "primary" : ""}`} onClick={() => setFilter(k)}>{l}</button>
            ))}
          </div>
          <div className="events">
            <table className="tbl">
              <thead><tr><th>Time</th><th>Type</th><th>Decision</th><th>Who / client</th><th>Detail</th></tr></thead>
              <tbody>
                {shown.length === 0 && <tr><td colSpan={5} className="muted">Waiting for activity… ask the copilot something in another tab.</td></tr>}
                {shown.map((e) => {
                  const [label, cls] = DECISION_PILL[e.decision] || [e.decision, "neutral"];
                  return (
                    <tr key={e.id} className={newIds.has(e.id) ? "ev-new" : ""}>
                      <td className="small mono">{time(e.ts)}</td>
                      <td className="small">{KIND_LABEL[e.kind] || e.kind}{e.lane ? <div className="muted">{e.lane} lane</div> : null}</td>
                      <td><span className={`pill ${cls}`}>{label}</span></td>
                      <td className="small">{e.employee || "client device"}{e.role ? <span className="muted"> ({e.role})</span> : null}{e.client_id ? <div className="muted">{e.client_id}</div> : null}</td>
                      <td className="small">{e.tool && <div className="mono">{e.tool}</div>}{e.detail}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card card-pad">
            <div className="card-title">Try to bypass the gateway</div>
            <p className="small muted" style={{ marginTop: 0 }}>Calls the core-banking MCP server directly — once with no gateway pass, once with a forged one.</p>
            <button className="btn sm primary" onClick={() => api.bypass().then(setBypass)}>Attempt direct MCP access</button>
            {bypass && bypass.attempts.map((a) => (
              <div key={a.attempt} className="small" style={{ marginTop: 8 }}>
                <span className={`pill ${a.refused ? "good" : "bad"}`}>{a.refused ? "Refused" : "SUCCEEDED"}</span> <b>{a.attempt}</b>
                <div className="muted mono" style={{ marginTop: 3 }}>{a.message.replace(/^Error executing tool \w+: /, "")}</div>
              </div>
            ))}
          </div>

          {policy && (
            <div className="card card-pad">
              <div className="card-title">Policy in force</div>
              <ol className="rules">{policy.rules.map((r) => <li key={r}>{r}</li>)}</ol>
            </div>
          )}

          {policy && (
            <div className="card card-pad">
              <div className="card-title">Who can reach what</div>
              <table className="tbl matrix">
                <thead><tr><th>Domain</th>{Object.keys(policy.roles).map((r) => <th key={r}>{policy.role_labels[r]}</th>)}</tr></thead>
                <tbody>
                  {Object.entries(policy.domains).map(([d, label]) => (
                    <tr key={d}><td>{label}{policy.consent_gated_domains.includes(d) ? " *" : ""}</td>
                      {Object.keys(policy.roles).map((r) => <td key={r}>{policy.roles[r].includes(d) ? "✓" : <span className="muted">—</span>}</td>)}</tr>
                  ))}
                </tbody>
              </table>
              <div className="small muted" style={{ marginTop: 6 }}>* also requires the client's consent for AI use</div>
            </div>
          )}

          {policy && (
            <div className="card card-pad">
              <div className="card-title">Tool registry</div>
              <div className="small">{Object.keys(policy.tool_registry).length} approved tools across 7 MCP servers.</div>
              {policy.unapproved_tools.length > 0 && (
                <div className="small" style={{ marginTop: 8 }}>
                  <span className="pill warn">Discovered, not approved</span>
                  {policy.unapproved_tools.map((t) => <div key={t} className="mono" style={{ marginTop: 4 }}>{t} — never shown to any model</div>)}
                </div>
              )}
              <div className="small muted" style={{ marginTop: 8 }}>Masked before any model sees them: {policy.masked_fields.join(", ")}.</div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
