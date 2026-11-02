import { useEffect, useState } from "react";
import { api } from "../api";
import { go } from "../App";
import { money, initials } from "../lib/format";

const FLAG_STYLE = { "High card utilization": "warn", "Upcoming cash need": "info", "AI wealth access withheld": "neutral", "Prepayment room": "good", "Unusual memo": "flag" };

export default function Clients({ user }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { api.clients().then((d) => setRows(d.clients)).catch((e) => setError(e.message)); }, []);
  if (error) return <div className="error-box">{error}</div>;
  if (!rows) return <p className="muted">Loading clients…</p>;
  const has = (k) => rows.some((r) => k in r);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{user.role === "teller" ? "Clients" : "My client book"}</h1>
          <p>{user.role === "teller" ? "You see deposits and cards. Other systems are restricted for your role." : `${rows.length} clients · Toronto — King & Bay`}</p>
        </div>
      </div>
      <div className="card">
        <table className="tbl">
          <thead>
            <tr>
              <th>Client</th>
              {has("risk_tolerance") && <th>Risk profile</th>}
              {has("deposits_total") && <th className="num">Deposits</th>}
              {has("card_balance") && <th className="num">Card balance</th>}
              {has("mortgage_balance") && <th className="num">Mortgage</th>}
              {has("wealth_total") && <th className="num">Investments</th>}
              {has("flags") && <th>Signals</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.client_id} className="clickable" onClick={() => go(`client/${r.client_id}`)}>
                <td>
                  <div className="row">
                    <div className="avatar">{initials(r.name)}</div>
                    <div>
                      <div style={{ fontWeight: 600 }}>{r.name}</div>
                      <div className="small muted">{r.segment} · client since {r.since}</div>
                    </div>
                  </div>
                </td>
                {has("risk_tolerance") && <td>{r.risk_tolerance}</td>}
                {has("deposits_total") && <td className="num">{money(r.deposits_total)}</td>}
                {has("card_balance") && <td className="num">{money(r.card_balance)}</td>}
                {has("mortgage_balance") && <td className="num">{r.mortgage_balance ? money(r.mortgage_balance) : "—"}</td>}
                {has("wealth_total") && <td className="num">{money(r.wealth_total)}</td>}
                {has("flags") && <td><div className="row" style={{ flexWrap: "wrap", gap: 4 }}>{r.flags.map((f) => <span key={f} className={`pill ${FLAG_STYLE[f] || "neutral"}`}>{f}</span>)}</div></td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
