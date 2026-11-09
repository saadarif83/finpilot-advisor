import { useEffect, useState, useCallback } from "react";
import { api, loadSession, saveSession, setUnauthorizedHandler } from "./api";
import Shell from "./components/Shell";
import Login from "./pages/Login";
import Clients from "./pages/Clients";
import ClientWorkspace from "./pages/ClientWorkspace";
import Research from "./pages/Research";
import Approvals from "./pages/Approvals";
import Governance from "./pages/Governance";
import Audit from "./pages/Audit";
import ApprovePage from "./pages/ApprovePage";

// Simple hash routes: #/clients, #/client/c-1001, #/research, #/approvals, #/governance, #/audit
function useHashRoute() {
  const read = () => (window.location.hash.replace(/^#\/?/, "") || "").split("/");
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const f = () => setRoute(read());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return route;
}
export const go = (path) => { window.location.hash = "/" + path; };

export default function App() {
  // The client's phone approval page lives at /approve/<id>?t=... and needs no sign-in.
  if (window.location.pathname.startsWith("/approve/")) return <ApprovePage />;
  return <EmployeeApp />;
}

function EmployeeApp() {
  const [session, setSession] = useState(loadSession);
  const route = useHashRoute();

  const signOut = useCallback(() => { saveSession(null); setSession(null); }, []);
  useEffect(() => { setUnauthorizedHandler(signOut); }, [signOut]);

  if (!session) {
    return <Login onSignedIn={(s) => { saveSession(s); setSession(s); go(defaultPage(s.user.role)); }} />;
  }

  const [page, arg] = route;
  const role = session.user.role;
  let body;
  if (page === "client" && arg) body = <ClientWorkspace key={arg} clientId={arg} user={session.user} />;
  else if (page === "research") body = <Research user={session.user} />;
  else if (page === "approvals") body = <Approvals user={session.user} selectedId={arg} />;
  else if (page === "governance") body = ["supervisor", "compliance"].includes(role) ? <Governance user={session.user} /> : <Restricted />;
  else if (page === "audit") body = <Audit key={arg || "list"} user={session.user} selectedId={arg} />;
  else if (page === "clients" || !page) body = role === "compliance" ? <Governance user={session.user} /> : <Clients user={session.user} />;
  else body = <Clients user={session.user} />;

  return (
    <Shell user={session.user} page={page || defaultPage(role)} onSignOut={signOut}
           onReset={async () => { if (confirm("Reset all clients, proposals, audit records and counters to the start?")) { await api.reset(); window.location.reload(); } }}>
      {body}
    </Shell>
  );
}

function Restricted() {
  return (
    <div className="card card-pad" style={{ maxWidth: 560 }}>
      <h3>🔒 Governance console is restricted</h3>
      <p className="muted" style={{ marginBottom: 0 }}>Bank-wide AI activity, policy and the kill switch are visible to Supervisors and Compliance only.</p>
    </div>
  );
}

function defaultPage(role) { return role === "compliance" ? "governance" : "clients"; }
