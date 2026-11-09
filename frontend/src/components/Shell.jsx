import { useEffect, useState } from "react";
import { api } from "../api";
import { go } from "../App";
import { initials } from "../lib/format";

const ROLE_LABEL = { advisor: "Advisor", teller: "Teller", supervisor: "Supervisor", compliance: "Compliance" };

export function Wordmark({ sub = true }) {
  return (
    <div className="wordmark">
      <div className="mark"><span /><span /><span /></div>
      Northstead Financial {sub && <span className="sub">Advisor Copilot</span>}
    </div>
  );
}

export default function Shell({ user, page, children, onSignOut, onReset }) {
  const [pending, setPending] = useState(0);
  useEffect(() => {
    if (user.role === "teller") return;
    let alive = true;
    const tick = () => api.proposals().then((d) => {
      if (!alive) return;
      const mine = d.proposals.filter((p) => user.role === "supervisor" ? p.status === "pending_supervisor" : ["draft", "pending_client"].includes(p.status));
      setPending(mine.length);
    }).catch(() => {});
    tick();
    const id = setInterval(tick, 4000);
    return () => { alive = false; clearInterval(id); };
  }, [user.role]);

  const nav = [
    user.role !== "compliance" && ["clients", "👥", "Clients"],
    ["research", "🔎", "Research"],
    user.role !== "teller" && ["approvals", "✅", "Approvals", pending],
  ].filter(Boolean);
  const canGovern = ["supervisor", "compliance"].includes(user.role);
  const gov = [canGovern && ["governance", "🛡️", "Governance console"], ["audit", "📜", canGovern ? "Audit trail" : "My audit trail"]].filter(Boolean);
  const active = page === "client" ? "clients" : page;

  return (
    <>
      <header className="topbar">
        <Wordmark />
        <span className="sim-pill">Demo · simulated bank</span>
        <div className="spacer" />
        <div className="user">
          <div className="avatar" style={{ width: 30, height: 30, fontSize: 12 }}>{initials(user.name)}</div>
          <div>
            <div style={{ fontWeight: 600 }}>{user.name}</div>
            <div style={{ color: "#9aa1ab", fontSize: 11.5 }}>{user.title}</div>
          </div>
          <span className="role-chip">{ROLE_LABEL[user.role]}</span>
        </div>
        <button className="ghost" onClick={onReset} title="Reset the demo data">↺ Reset demo</button>
        <button className="ghost" onClick={onSignOut}>Switch user</button>
      </header>
      <div className="layout">
        <aside className="sidebar">
          <div className="section">Work</div>
          {nav.map(([key, ico, label, count]) => (
            <button key={key} className={`nav ${active === key ? "active" : ""}`} onClick={() => go(key)}>
              <span>{ico}</span>{label}{count ? <span className="count">{count}</span> : null}
            </button>
          ))}
          <div className="section">Governance</div>
          {gov.map(([key, ico, label]) => (
            <button key={key} className={`nav ${active === key ? "active" : ""}`} onClick={() => go(key)}>
              <span>{ico}</span>{label}
            </button>
          ))}
          <div className="foot">
            Every AI request goes through the <b>Northstead MCP gateway</b>. Client data stays on the private model lane.
            <br /><br />Fictional bank and clients. The private lane is simulated for this demo.
          </div>
        </aside>
        <main className="page">{children}</main>
      </div>
    </>
  );
}
