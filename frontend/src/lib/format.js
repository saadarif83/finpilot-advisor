export const money = (n, digits = 0) =>
  n == null ? "—" : Number(n).toLocaleString("en-CA", { style: "currency", currency: "CAD", minimumFractionDigits: digits, maximumFractionDigits: digits });
export const money2 = (n) => money(n, 2);
export const bytes = (b) => (b < 1024 ? `${b} B` : b < 1024 * 1024 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(2)} MB`);
export const time = (ts) => new Date(ts * 1000).toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
export const initials = (name) => name.split(/\s+|&/).filter(Boolean).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
export const prettyTool = (t) => (t || "").replace("__", ".");
export const STATUS_LABEL = {
  draft: ["Draft — not sent", "neutral"],
  pending_client: ["Awaiting client", "warn"],
  pending_supervisor: ["Awaiting supervisor co-sign", "warn"],
  executed: ["Executed", "good"],
  declined: ["Declined", "bad"],
  failed: ["Refused / failed", "bad"],
  discarded: ["Discarded", "neutral"],
};
export const DECISION_PILL = {
  allowed: ["Allowed", "good"],
  masked: ["Allowed · masked", "info"],
  flagged: ["Flagged", "flag"],
  denied: ["Denied", "bad"],
  blocked: ["Blocked", "bad"],
  routed: ["Routed", "neutral"],
  info: ["Info", "neutral"],
};
