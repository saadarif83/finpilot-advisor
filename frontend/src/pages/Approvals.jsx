import { useEffect, useState } from "react";
import { api } from "../api";
import { go } from "../App";
import { money2, STATUS_LABEL, time } from "../lib/format";
import QrModal from "../components/QrModal";

export default function Approvals({ user, selectedId }) {
  const [list, setList] = useState(null);
  const [sel, setSel] = useState(selectedId || null);
  const [qr, setQr] = useState(null);
  const [err, setErr] = useState(null);

  const load = () => api.proposals().then((d) => setList(d.proposals)).catch((e) => setErr(e.message));
  useEffect(() => { load(); const id = setInterval(load, 2000); return () => clearInterval(id); }, []);
  if (err) return <div className="error-box">{err}</div>;
  if (!list) return <p className="muted">Loading…</p>;
  const p = list.find((x) => x.id === sel) || null;

  async function act(fn) {
    setErr(null);
    try { await fn(); await load(); } catch (e) { setErr(e.message); }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Approvals</h1>
          <p>The copilot can only propose. Money moves after the client approves on their own device{user.role === "supervisor" ? " — and you co-sign anything above the threshold." : ", plus a supervisor co-sign above the threshold."}</p>
        </div>
      </div>
      {err && <div className="error-box" style={{ marginBottom: 12 }}>{err}</div>}
      <div className="split">
        <div className="card">
          <table className="tbl">
            <thead><tr><th>Proposal</th><th>Client</th><th className="num">Amount</th><th>Status</th></tr></thead>
            <tbody>
              {list.length === 0 && <tr><td colSpan={4} className="muted">No proposals yet. Ask the copilot to suggest an action from a client's workspace.</td></tr>}
              {list.map((x) => {
                const [label, cls] = STATUS_LABEL[x.status] || [x.status, "neutral"];
                return (
                  <tr key={x.id} className="clickable" onClick={() => setSel(x.id)} style={sel === x.id ? { outline: "2px solid var(--brand-black)", outlineOffset: -2 } : null}>
                    <td><div style={{ fontWeight: 600 }}>{x.title}</div><div className="small muted">{x.id} · by {x.created_by_name}</div></td>
                    <td>{x.client_name}</td>
                    <td className="num">{money2(x.amount)}</td>
                    <td><span className={`pill ${cls}`}>{label}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="card card-pad">
          {!p ? <p className="muted">Select a proposal to see its approvals and history.</p> : (
            <>
              <div className="row"><h3>{p.title}</h3><div className="spacer" /><span className={`pill ${(STATUS_LABEL[p.status] || [])[1]}`}>{(STATUS_LABEL[p.status] || [p.status])[0]}</span></div>
              <p className="muted" style={{ margin: "6px 0" }}>{p.client_name} · prepared by {p.created_by_name} with the AI copilot · {p.id}</p>
              <p style={{ lineHeight: 1.5 }}>{p.rationale}</p>

              <div className="section-h">Exact action (frozen)</div>
              <pre className="json">{JSON.stringify({ type: p.type, params: p.params }, null, 2)}</pre>
              <div className="hash" style={{ marginTop: 6 }}>SHA-256 {p.args_hash}</div>

              <div className="section-h">Approvals</div>
              {p.approvals.length === 0 && <div className="muted small">None yet.</div>}
              {p.approvals.map((a, i) => (
                <div key={i} className="small" style={{ marginBottom: 6 }}>
                  <span className={`pill ${a.decision === "approved" ? "good" : "bad"}`}>{a.role} {a.decision}</span>{" "}
                  {a.name} · {time(a.at)} <span className="hash">sig {a.signature.slice(0, 14)}…</span>
                </div>
              ))}

              <div className="row" style={{ marginTop: 12, flexWrap: "wrap" }}>
                {p.status === "draft" && ["advisor", "supervisor"].includes(user.role) && (
                  <button className="btn primary sm" onClick={() => act(async () => { const np = await api.sendProposal(p.id); setQr(np); })}>Send to client</button>)}
                {p.status === "pending_client" && <button className="btn sm" onClick={() => setQr(p)}>Show approval QR</button>}
                {p.status === "pending_supervisor" && user.role === "supervisor" && <>
                  <button className="btn primary sm" onClick={() => act(() => api.cosign(p.id, "approved"))}>Co-sign & release</button>
                  <button className="btn sm" onClick={() => act(() => api.cosign(p.id, "declined"))}>Decline</button>
                </>}
                {p.status === "pending_supervisor" && user.role !== "supervisor" && <span className="small muted">Waiting for a supervisor. Switch user to Morgan Wright (in another tab) to co-sign.</span>}
                {p.status === "pending_supervisor" && (
                  <button className="btn sm" title="Demo: change the amount after the client approved" onClick={() => act(() => api.tamper(p.id))}>⚠ Simulate tampering</button>)}
                {["draft", "pending_client"].includes(p.status) && ["advisor", "supervisor"].includes(user.role) && (
                  <button className="btn sm" onClick={() => act(() => api.discardProposal(p.id))}>Discard</button>)}
              </div>

              {p.execution && (
                <>
                  <div className="section-h">Executor result</div>
                  <div className={p.execution.ok ? "pill good" : "error-box small"}>{p.execution.ok ? "✓ Executed — both ledger writes completed" : p.execution.error}</div>
                </>
              )}

              <div className="section-h">History</div>
              <div className="timeline">
                {p.history.map((h, i) => (
                  <div key={i} className="t"><b>{h.event.replaceAll("_", " ")}</b> · {h.by} <span className="muted">· {time(h.at)}</span>{h.detail && <div className="muted">{h.detail}</div>}</div>
                ))}
              </div>
              {p.audit_id && <p className="small" style={{ marginTop: 14 }}><a href="#" onClick={(e) => { e.preventDefault(); go(`audit/${p.audit_id}`); }}>Open audit record {p.audit_id} →</a></p>}
            </>
          )}
        </div>
      </div>
      {qr && <QrModal proposal={qr} onClose={() => setQr(null)} />}
    </>
  );
}
