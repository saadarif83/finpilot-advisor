import { useEffect, useState } from "react";
import { api } from "../api";
import { Wordmark } from "../components/Shell";
import { initials } from "../lib/format";

const ROLE_NOTE = {
  advisor: "Full client book · can prepare proposals",
  teller: "Deposits & cards only",
  supervisor: "Co-signs large money movements",
  compliance: "Audit and governance, no client book",
};

export default function Login({ onSignedIn }) {
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState("jordan.lee");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [waking, setWaking] = useState(true);

  useEffect(() => {
    api.users().then((d) => { setUsers(d.users); setWaking(false); })
      .catch(() => setError("Can't reach the backend. If it's on Render's free tier it may be waking up — wait 30–60 seconds and refresh."));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await api.login(selected, password);
      onSignedIn({ token: r.access_token, user: r.user });
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <div className="login-wrap">
      <div className="login-hero">
        <Wordmark />
        <div>
          <h1>Advisor Copilot</h1>
          <div className="redbar" />
          <p style={{ marginTop: 24 }}>
            AI assistance for client reviews, built inside the bank's perimeter: every model and tool call goes through
            a governing gateway, client data never leaves the private lane, and nothing moves money without a human.
          </p>
        </div>
        <p className="small">Fictional bank, clients and data · demonstration only</p>
      </div>
      <div className="login-panel">
        <form className="login-box" onSubmit={submit}>
          <h2>Sign in with Northstead SSO</h2>
          <p className="muted" style={{ marginTop: 0 }}>Simulated single sign-on. Pick an employee to see how access changes by role.</p>
          {waking && !error && <p className="muted">Connecting…</p>}
          {users.map((u) => (
            <button type="button" key={u.username} className={`user-option ${selected === u.username ? "selected" : ""}`} onClick={() => setSelected(u.username)}>
              <div className="avatar">{initials(u.name)}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600 }}>{u.name} <span className="chip" style={{ marginLeft: 6 }}>{u.role}</span></div>
                <div className="small muted">{u.title} · {ROLE_NOTE[u.role]}</div>
              </div>
            </button>
          ))}
          <label className="field">
            <span>Password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <div className="error-box" style={{ marginBottom: 12 }}>{error}</div>}
          <button className="btn primary" style={{ width: "100%", padding: 12 }} disabled={busy || !users.length}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
