import { useState } from "react";
import { api } from "../api";
import { money2, STATUS_LABEL } from "../lib/format";
import QrModal from "./QrModal";

const LABELS = { card_balance: "Card balance", source_balance: "Source account", mortgage_balance: "Mortgage balance", gic_balance: "New GIC" };
const CHECK_ICON = { pass: "✅", adjusted: "✏️", fail: "❌" };

export default function ProposalCard({ proposal, canSend }) {
  const [p, setP] = useState(proposal);
  const [qr, setQr] = useState(false);
  const [err, setErr] = useState(null);
  const [label, cls] = STATUS_LABEL[p.status] || [p.status, "neutral"];
  const before = p.summary?.before || {};
  const after = p.summary?.after || {};
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])];

  async function send() {
    setErr(null);
    try { const np = await api.sendProposal(p.id); setP(np); setQr(true); } catch (e) { setErr(e.message); }
  }

  return (
    <div className="proposal">
      <div className="p-title">💡 {p.title}<div className="spacer" /><span className={`pill ${cls}`}>{label}</span></div>
      <div className="p-rat">{p.rationale}</div>
      <div className="ba">
        <span className="h">From: {p.summary?.source}</span><span className="h">Before</span><span /><span className="h">After</span>
        {keys.map((k) => (
          <FragmentRow key={k} label={LABELS[k] || k} a={before[k]} b={after[k]} />
        ))}
      </div>
      <div className="checks">
        {p.checks.map((c, i) => <div key={i}><span>{CHECK_ICON[c.result] || "•"}</span><span><b>{c.check}:</b> {c.detail}</span></div>)}
      </div>
      <div className="small" style={{ marginBottom: 8 }}>
        <b>Estimated benefit:</b> {money2(p.summary?.estimated_annual_benefit)} / year ·{" "}
        {p.needs_cosign ? "Needs client approval + supervisor co-sign" : "Needs client approval"}
      </div>
      <div className="hash" style={{ marginBottom: 10 }}>{p.id} · action hash {p.args_hash.slice(0, 16)}… · the AI cannot execute this</div>
      {err && <div className="error-box small" style={{ marginBottom: 8 }}>{err}</div>}
      {canSend && p.status === "draft" && <button className="btn primary sm" onClick={send}>Send to client for approval</button>}
      {p.status !== "draft" && p.approval_url && <button className="btn sm" onClick={() => setQr(true)}>Show approval QR</button>}
      {qr && <QrModal proposal={p} onClose={() => { setQr(false); api.proposal(p.id).then(setP).catch(() => {}); }} />}
    </div>
  );
}

function FragmentRow({ label, a, b }) {
  return (<><span>{label}</span><span>{a != null ? money2(a) : "—"}</span><span className="muted">→</span><span><b>{b != null ? money2(b) : "—"}</b></span></>);
}
