// Every call to the backend goes through here.
export const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || "http://localhost:8000").replace(/\/+$/, "");

const KEY = "northstead.session";
// sessionStorage = one sign-in per browser tab, so you can be the Advisor in
// one tab and the Supervisor in another during the demo.
export function loadSession() {
  try { return JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch { return null; }
}
export function saveSession(s) {
  try { s ? sessionStorage.setItem(KEY, JSON.stringify(s)) : sessionStorage.removeItem(KEY); } catch { /* ignore */ }
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) { onUnauthorized = fn; }

async function request(method, path, body, { auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  const s = loadSession();
  if (auth && s?.token) headers.Authorization = `Bearer ${s.token}`;
  const res = await fetch(`${BACKEND_URL}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (res.status === 401 && auth) { onUnauthorized(); throw new Error("Signed out"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

export const api = {
  users: () => request("GET", "/auth/users", null, { auth: false }),
  login: (username, password) => request("POST", "/auth/login", { username, password }, { auth: false }),
  clients: () => request("GET", "/workspace/clients"),
  client: (id) => request("GET", `/workspace/clients/${id}`),
  lanes: () => request("GET", "/copilot/lanes"),
  proposals: () => request("GET", "/proposals"),
  proposal: (id) => request("GET", `/proposals/${id}`),
  sendProposal: (id) => request("POST", `/proposals/${id}/send`),
  discardProposal: (id) => request("POST", `/proposals/${id}/discard`),
  cosign: (id, decision) => request("POST", `/proposals/${id}/cosign`, { decision }),
  tamper: (id) => request("POST", `/proposals/${id}/demo-tamper`),
  events: (since) => request("GET", `/gateway/events?since=${since}`),
  stats: () => request("GET", "/gateway/stats"),
  policy: () => request("GET", "/gateway/policy"),
  killSwitch: (enabled) => request("POST", "/gateway/killswitch", { enabled }),
  bypass: () => request("POST", "/gateway/demo/bypass"),
  audits: () => request("GET", "/audit"),
  audit: (id) => request("GET", `/audit/${id}`),
  reset: () => request("POST", "/admin/reset"),
  clientApproval: (id, t) => request("GET", `/client-approval/${id}?t=${encodeURIComponent(t)}`, null, { auth: false }),
  clientDecide: (id, t, decision) => request("POST", `/client-approval/${id}`, { t, decision }, { auth: false }),
};

// Copilot answers stream as Server-Sent Events over a POST.
export async function streamCopilot(body, onEvent) {
  const s = loadSession();
  const res = await fetch(`${BACKEND_URL}/copilot/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${s?.token}` },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { onUnauthorized(); throw new Error("Signed out"); }
  if (!res.ok || !res.body) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail || "Copilot request failed");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const p of parts) {
      const line = p.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try { onEvent(JSON.parse(line.slice(6))); } catch { /* skip malformed */ }
    }
  }
}
