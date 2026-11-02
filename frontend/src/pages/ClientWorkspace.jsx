import { useEffect, useState } from "react";
import { api } from "../api";
import { go } from "../App";
import { money, money2, initials } from "../lib/format";
import Copilot from "../components/Copilot";
import { CashflowChart, SpendingChart, PerformanceChart } from "../components/Charts";

// Demo prompts per client — each one exercises a different part of the architecture.
const SUGGESTIONS = {
  "c-1001": [
    { tag: "Briefing", q: "Give me a 30-second briefing on Aisha before our meeting." },
    { tag: "Propose an action", q: "Aisha is carrying a balance on her Visa. Should she pay it down, and from where?" },
  ],
  "c-1002": [
    { tag: "Untrusted data", q: "Review Daniel's recent account activity. Anything I should know?" },
    { tag: "Suitability", q: "Daniel has a lot sitting in savings. Could he earn more in a GIC without hurting his renovation plans?" },
  ],
  "c-1003": [
    { tag: "Propose an action", q: "Mei Lin's card balance is high. What's the best way to bring it down?" },
    { tag: "Briefing", q: "Summarize Mei Lin's finances and her biggest risk." },
  ],
  "c-1004": [
    { tag: "Policy limits", q: "Should the Tremblays make a lump-sum mortgage prepayment this year? How much can they do?" },
    { tag: "Suitability", q: "They'd like to prepay $40,000 — can they?" },
  ],
  "c-1005": [
    { tag: "Consent", q: "Give me the full picture of Marco's finances, including his investments." },
    { tag: "Propose an action", q: "Should Marco pay down his business Visa?" },
  ],
};
const GENERIC = [{ tag: "Briefing", q: "Give me a quick briefing on this client." }];

function Locked({ title, reason }) {
  return (
    <div className="card tile locked">
      <div className="label">{title}</div>
      <div className="value">🔒 Restricted</div>
      <div className="sub">{reason}</div>
    </div>
  );
}

export default function ClientWorkspace({ clientId, user }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () => api.client(clientId).then((x) => alive && setD(x)).catch((e) => alive && setError(e.message));
    load();
    const id = setInterval(load, 5000); // reflect approved actions live
    return () => { alive = false; clearInterval(id); };
  }, [clientId]);

  if (error) return <div className="error-box">{error}</div>;
  if (!d) return <p className="muted">Loading client…</p>;
  const { header, profile, core, cards, mortgage, wealth, ai_consent } = d;
  const hasProfile = !profile.restricted;

  return (
    <div className="ws">
      <div className="ws-main">
        <div><a href="#/clients" onClick={(e) => { e.preventDefault(); go("clients"); }}>← Clients</a></div>
        <div className="card client-head">
          <div className="avatar">{initials(header.name)}</div>
          <div>
            <h1>{header.name}</h1>
            <div className="muted small">{header.segment} · client since {header.since}{hasProfile && <> · {profile.risk_tolerance} · {profile.time_horizon}</>}</div>
          </div>
          <div className="spacer" />
          <div style={{ textAlign: "right" }}>
            <div className="small muted" style={{ marginBottom: 4 }}>AI data consent</div>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <span className={`pill ${ai_consent.ai_assist ? "good" : "bad"}`}>{ai_consent.ai_assist ? "✓" : "✕"} AI assistance</span>
              <span className={`pill ${ai_consent.wealth ? "good" : "neutral"}`}>{ai_consent.wealth ? "✓ Wealth data" : "✕ Wealth data withheld"}</span>
            </div>
          </div>
        </div>

        <div className="tiles">
          {core.restricted ? <Locked title="Deposits" reason={core.reason} /> : (
            <div className="card tile"><div className="label">Deposits</div><div className="value">{money(core.total)}</div>
              <div className="sub">{core.accounts.length} accounts</div></div>)}
          {cards.restricted ? <Locked title="Credit card" reason={cards.reason} /> : (
            <div className="card tile"><div className="label">Credit card · {cards.card.apr}% APR</div><div className="value">{money(cards.card.balance)}</div>
              <div className="meter"><div style={{ width: `${Math.min(100, cards.card.utilization_pct)}%` }} /></div>
              <div className="sub">{cards.card.utilization_pct}% of {money(cards.card.credit_limit)} limit</div></div>)}
          {mortgage.restricted ? <Locked title="Mortgage" reason={mortgage.reason} /> : (
            <div className="card tile"><div className="label">Mortgage</div>
              {mortgage.mortgage ? <>
                <div className="value">{money(mortgage.mortgage.balance)}</div>
                <div className="sub">{mortgage.mortgage.rate}% {mortgage.mortgage.rate_type} · prepay room {money(mortgage.privilege.remaining_this_year)}</div>
              </> : <><div className="value" style={{ color: "var(--text-3)" }}>None</div><div className="sub">No mortgage with WWT</div></>}
            </div>)}
          {wealth.restricted ? <Locked title="Investments" reason={wealth.reason} /> : (
            <div className="card tile"><div className="label">Investments</div><div className="value">{money(wealth.total)}</div>
              <div className="sub">{money(wealth.cash)} uninvested cash</div></div>)}
        </div>

        <div className="grid2">
          {!core.restricted && <div className="card card-pad"><div className="card-title">Money in vs. money out</div><CashflowChart data={core.cashflow} /></div>}
          {!cards.restricted && <div className="card card-pad"><div className="card-title">Card spending by category · Oct 2026</div><SpendingChart data={cards.spending} /></div>}
          {!wealth.restricted && <div className="card card-pad"><div className="card-title">Portfolio value, last 6 months</div><PerformanceChart data={wealth.performance} /></div>}
          {hasProfile && (
            <div className="card card-pad">
              <div className="card-title">Client profile (KYC)</div>
              <dl className="kv">
                <dt>Risk tolerance</dt><dd>{profile.risk_tolerance}</dd>
                <dt>Time horizon</dt><dd>{profile.time_horizon}</dd>
                <dt>Liquidity needs</dt><dd>{profile.liquidity_needs}</dd>
                <dt>Monthly expenses</dt><dd>{money(profile.monthly_expenses)}</dd>
                <dt>Goals</dt><dd>{profile.goals.join(" · ")}</dd>
                <dt>KYC</dt><dd>{profile.kyc_status}</dd>
                <dt>SIN</dt><dd className="mono">{profile.sin}</dd>
                <dt>Contact</dt><dd className="mono">{profile.email} · {profile.phone}</dd>
              </dl>
            </div>
          )}
        </div>

        {!core.restricted && (
          <div className="card">
            <div className="card-pad" style={{ paddingBottom: 0 }}><div className="card-title">Accounts</div></div>
            <table className="tbl">
              <thead><tr><th>Account</th><th>Number</th><th className="num">Rate</th><th className="num">Balance</th></tr></thead>
              <tbody>
                {core.accounts.map((a) => <tr key={a.account_id}><td>{a.name}</td><td className="mono">{a.account_number}</td><td className="num">{a.rate ? `${a.rate}%` : "—"}</td><td className="num">{money2(a.balance)}</td></tr>)}
                {!wealth.restricted && wealth.accounts.map((a) => <tr key={a.account_id}><td>{a.type} (investment cash)</td><td className="mono">{a.account_number}</td><td className="num">—</td><td className="num">{money2(a.cash)}</td></tr>)}
              </tbody>
            </table>
          </div>
        )}

        {!core.restricted && (
          <div className="card">
            <div className="card-pad" style={{ paddingBottom: 0 }}><div className="card-title">Recent deposit activity</div></div>
            <table className="tbl">
              <thead><tr><th>Date</th><th>Description</th><th className="num">Amount</th></tr></thead>
              <tbody>
                {core.recent_transactions.map((t) => (
                  <tr key={t.id}>
                    <td className="small">{t.date}</td>
                    <td>{t.desc}{t.memo && <div className={`memo ${/instruction/i.test(t.memo) ? "suspicious" : ""}`}>Memo: “{t.memo}”</div>}</td>
                    <td className="num" style={{ color: t.amount < 0 ? "var(--text)" : "var(--good)" }}>{money2(t.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Copilot mode="client" clientId={clientId} clientName={header.name} user={user}
        suggestions={user.role === "teller" ? [{ tag: "Role limits", q: `How is ${header.name.split(" ")[0]}'s investment portfolio doing?` }, ...GENERIC] : (SUGGESTIONS[clientId] || GENERIC)} />
    </div>
  );
}
