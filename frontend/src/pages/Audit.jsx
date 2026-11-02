import { useEffect, useState } from "react";
import { api } from "../api";
import { go } from "../App";
import { time, bytes, prettyTool, DECISION_PILL, STATUS_LABEL, money2 } from "../lib/format";

export default function Audit({ user, selectedId }) {
  const [list, setList] = useState(null);
  const [rec, setRec] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => { api.audits().then((d) => setList(d.records)).catch((e) => setErr(e.message)); }, []);
  useEffect(() => {
    if (!selectedId) { setRec(null); return; }
    api.audit(selectedId).then(setRec).catch((e) => setErr(e.message));
  }, [selectedId]);

  if (err) return <div className="error-box">{err}</div>;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Audit trail</h1>
          <p>One evidence record per copilot request{user.role === "compliance" || user.role === "supervisor" ? " — all employees." : " — your requests."}</p>
        </div>
      </div>
      <div className="split">
        <div className="card">
          <table className="tbl">
            <thead><tr><th>Record</th><th>Who / client</th><th>Lane</th><th>Result</th></tr></thead>
            <tbody>
              {!list && <tr><td colSpan={4} className="muted">Loading…</td></tr>}
              {list && list.length === 0 && <tr><td colSpan={4} className="muted">No records yet.</td></tr>}
              {list && list.map((r) => (
                <tr key={r.id} className="clickable" onClick={() => go(`audit/${r.id}`)} style={selectedId === r.id ? { outline: "2px solid var(--brand-black)", outlineOffset: -2 } : null}>
                  <td><div className="mono">{r.id}</div><div className="small muted">{time(r.started_at)}</div></td>
                  <td className="small">{r.employee.name} <span className="muted">({r.employee.role})</span><div className="muted">{r.client ? r.client.name : "Research (no client)"}</div></td>
                  <td className="small">{r.lane === "private" ? "🔒 private" : "🌐 external"}</td>
                  <td className="small">
                    <span className={`pill ${r.outcome === "answered" ? "good" : r.outcome === "blocked" ? "bad" : "neutral"}`}>{r.outcome}</span>
                    <div className="muted" style={{ marginTop: 3 }}>{r.tool_count} tools{r.denied ? ` · ${r.denied} denied` : ""}{r.flags ? ` · ${r.flags} flagged` : ""}{r.proposals ? ` · ${r.proposals} proposal` : ""}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card card-pad">
          {!rec ? <p className="muted">Select a record to see the full evidence.</p> : <Record rec={rec} />}
        </div>
      </div>
    </>
  );
}

function Record({ rec }) {
  const egress = rec.model_calls.reduce((s, m) => s + m.egress_bytes, 0);
  return (
    <>
      <div className="row"><h3 className="mono">{rec.id}</h3><div className="spacer" /><span className={`pill ${rec.outcome === "answered" ? "good" : "bad"}`}>{rec.outcome}</span></div>
      <dl className="kv" style={{ marginTop: 12 }}>
        <dt>Employee</dt><dd>{rec.employee.name} · {rec.employee.role}</dd>
        <dt>Client</dt><dd>{rec.client ? `${rec.client.name} (${rec.client.client_id})` : "None — research mode"}</dd>
        <dt>When</dt><dd>{time(rec.started_at)}{rec.finished_at ? ` – ${time(rec.finished_at)}` : ""}</dd>
        <dt>Question</dt><dd>“{rec.question}”</dd>
        <dt>Model lane</dt><dd>{rec.lane} · {rec.model} · {rec.model_calls.length} call(s)</dd>
        <dt>Data egress</dt><dd>{bytes(egress)}{rec.lane === "private" ? " (in-perimeter lane — simulated in this demo)" : ""}</dd>
        <dt>Data domains</dt><dd>{rec.data_domains.join(", ") || "none"}</dd>
        <dt>Fields masked</dt><dd>{[...new Set(rec.masked_fields.map((m) => m.split(".").pop().replace(/\[\d+\]/, "")))].join(", ") || "none"}</dd>
      </dl>

      <div className="section-h">Tool calls & gateway decisions</div>
      {rec.tool_calls.length === 0 && <div className="small muted">None.</div>}
      {rec.tool_calls.map((t, i) => {
        const [label, cls] = DECISION_PILL[t.decision] || [t.decision, "neutral"];
        return (
          <div key={i} className="small" style={{ marginBottom: 6 }}>
            <span className={`pill ${cls}`}>{label}</span> <span className="mono">{prettyTool(t.tool)}</span>
            {t.reason && <span className="muted"> — {t.reason}</span>}
            {t.proposal_id && <span className="muted"> → {t.proposal_id}</span>}
          </div>
        );
      })}

      {rec.injection_flags.length > 0 && (<>
        <div className="section-h">Untrusted-content flags</div>
        {rec.injection_flags.map((f, i) => <div key={i} className="memo suspicious small">{f.field}: “{f.excerpt}”</div>)}
      </>)}

      {rec.proposal_details?.length > 0 && (<>
        <div className="section-h">Proposals & approvals</div>
        {rec.proposal_details.map((p) => {
          const [label, cls] = STATUS_LABEL[p.status] || [p.status, "neutral"];
          return (
            <div key={p.id} className="small" style={{ marginBottom: 8 }}>
              <b>{p.id}</b> {p.title} · {money2(p.amount)} <span className={`pill ${cls}`}>{label}</span>
              <div className="hash">hash {p.args_hash.slice(0, 24)}…</div>
              {p.approvals.map((a, i) => <div key={i} className="muted">✍ {a.role} {a.decision} — {a.name} · sig {a.signature.slice(0, 12)}…</div>)}
              {p.execution && <div className={p.execution.ok ? "" : "memo suspicious"}>{p.execution.ok ? "Executed by deterministic executor" : p.execution.error}</div>}
            </div>
          );
        })}
      </>)}

      {rec.answer && (<>
        <div className="section-h">Answer given</div>
        <div className="small" style={{ whiteSpace: "pre-wrap", color: "var(--text-2)", maxHeight: 200, overflow: "auto" }}>{rec.answer}</div>
      </>)}

      <div className="section-h">Raw record</div>
      <pre className="json">{JSON.stringify(rec, null, 2)}</pre>
    </>
  );
}
