import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { api } from "../api";
import { money2, STATUS_LABEL } from "../lib/format";

// Shown after "Send to client": the client scans this with their phone and
// approves on their own device. Polls so the status updates live on screen.
export default function QrModal({ proposal, onClose }) {
  const [img, setImg] = useState(null);
  const [p, setP] = useState(proposal);
  useEffect(() => { if (p.approval_url) QRCode.toDataURL(p.approval_url, { margin: 1, width: 400 }).then(setImg); }, [p.approval_url]);
  useEffect(() => {
    const id = setInterval(() => api.proposal(p.id).then(setP).catch(() => {}), 2000);
    return () => clearInterval(id);
  }, [p.id]);
  const [label, cls] = STATUS_LABEL[p.status] || [p.status, "neutral"];

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="row"><h3>Client approval request</h3><div className="spacer" /><button className="btn sm" onClick={onClose}>Close</button></div>
        <p className="muted" style={{ marginBottom: 0 }}>{p.client_name} approves on their own device. The approval is bound to this exact action.</p>
        <div className="qr-wrap">
          {img ? <img src={img} alt="Approval link QR code" /> : <div style={{ width: 200, height: 200 }} />}
          <div>
            <div style={{ fontWeight: 700 }}>{p.title}</div>
            <div className="small muted" style={{ margin: "4px 0 10px" }}>{p.id} · {money2(p.amount)}</div>
            <span className={`pill ${cls}`}>{label}</span>
            {p.needs_cosign && <div className="small muted" style={{ marginTop: 8 }}>Above threshold — a supervisor co-sign follows the client's approval.</div>}
            <div className="hash" style={{ marginTop: 10 }}>Action hash {p.args_hash.slice(0, 16)}…</div>
          </div>
        </div>
        <div className="row">
          <a className="btn sm" href={p.approval_url} target="_blank" rel="noreferrer">Open client view in a new tab</a>
          <button className="btn sm" onClick={() => navigator.clipboard?.writeText(p.approval_url)}>Copy link</button>
        </div>
      </div>
    </div>
  );
}
