import { useEffect, useState } from "react";
import { api } from "../api";
import { Wordmark } from "../components/Shell";
import { money2 } from "../lib/format";

// The client's phone. Opened from the QR code; no employee sign-in.
export default function ApprovePage() {
  const id = window.location.pathname.split("/")[2];
  const t = new URLSearchParams(window.location.search).get("t") || "";
  const [p, setP] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => { api.clientApproval(id, t).then(setP).catch((e) => setErr(e.message)); }, [id, t]);

  async function decide(decision) {
    setBusy(true); setErr(null);
    try { setResult(await api.clientDecide(id, t, decision)); } catch (e) { setErr(e.message); } finally { setBusy(false); }
  }

  const s = p?.summary || {};
  const dest = p?.type === "card_payoff" ? "Credit card" : p?.type === "mortgage_prepayment" ? "Mortgage principal" : p?.summary?.product?.name || "GIC";

  return (
    <div className="phone">
      <div className="phone-top"><Wordmark sub={false} /></div>
      <div className="phone-body">
        {err && <div className="error-box">{err}</div>}
        {!p && !err && <p className="muted">Loading your request…</p>}
        {p && !result && p.status === "pending_client" && (
          <>
            <div className="card card-pad">
              <div className="small muted">Approval request · {p.id}</div>
              <h2 style={{ fontSize: 19, margin: "6px 0 2px" }}>Hi {p.client_name.split(" ")[0]}, please review</h2>
              <div className="small muted">Requested by your advisor, {p.created_by_name}</div>
              <div className="amount" style={{ margin: "16px 0 6px" }}>{money2(p.amount)}</div>
              <div className="flow">
                <div className="box"><div className="small muted">From</div><b>{s.source}</b></div>
                <div>→</div>
                <div className="box"><div className="small muted">To</div><b>{dest}</b></div>
              </div>
              <p style={{ lineHeight: 1.5, color: "var(--text-2)" }}>{p.rationale}</p>
            </div>
            <div className="card card-pad small">
              🔐 Your approval is signed for <b>exactly this amount and these accounts</b>. If anything changes, it can't be executed.
              <div className="hash" style={{ marginTop: 6 }}>Fingerprint {p.args_hash.slice(0, 20)}…</div>
              {p.needs_cosign && <div style={{ marginTop: 6 }}>Because of the amount, a branch supervisor will also review it.</div>}
            </div>
            <button className="btn primary" disabled={busy} onClick={() => decide("approved")}>Approve</button>
            <button className="btn" disabled={busy} onClick={() => decide("declined")}>Decline</button>
          </>
        )}
        {p && !result && p.status !== "pending_client" && (
          <div className="card done"><div className="big">ℹ️</div><p>This request is already <b>{p.status.replaceAll("_", " ")}</b>.</p></div>
        )}
        {result && (
          <div className="card done">
            <div className="big">{result.status === "declined" ? "✋" : result.status === "executed" ? "✅" : "⏳"}</div>
            <h2 style={{ fontSize: 20 }}>{result.status === "declined" ? "Declined" : result.status === "executed" ? "Done" : "Approved"}</h2>
            <p className="muted">
              {result.status === "declined" ? "Nothing will happen. Your advisor has been notified."
                : result.status === "executed" ? `${money2(result.amount)} has been moved as requested.`
                : "Thanks. A branch supervisor will complete the final review shortly."}
            </p>
          </div>
        )}
        <p className="small muted" style={{ textAlign: "center" }}>WWT Financials is a fictional bank used for a demonstration.</p>
      </div>
    </div>
  );
}
