// Tiny, safe markdown renderer for copilot replies: paragraphs, bullets,
// numbered lists, **bold**, *italic*, `code`, and #/##/### headings.
// It builds React elements (never raw HTML), so nothing can inject markup.
function inline(text, key) {
  const parts = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let last = 0, m, i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) parts.push(<strong key={`${key}-${i++}`}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) parts.push(<code key={`${key}-${i++}`}>{tok.slice(1, -1)}</code>);
    else parts.push(<em key={`${key}-${i++}`}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export default function Markdown({ text }) {
  const lines = (text || "").split("\n");
  const out = [];
  let list = null;
  const flush = () => { if (list) { out.push(list.ordered ? <ol key={out.length}>{list.items}</ol> : <ul key={out.length}>{list.items}</ul>); list = null; } };
  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)/);
    const num = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (bullet || num) {
      const ordered = !!num && !bullet;
      if (!list || list.ordered !== ordered) { flush(); list = { ordered, items: [] }; }
      list.items.push(<li key={idx}>{inline((bullet || num)[1], idx)}</li>);
      return;
    }
    flush();
    if (!line.trim()) return;
    const h = line.match(/^#{1,4}\s+(.*)/);
    if (h) out.push(<h4 key={idx}>{inline(h[1], idx)}</h4>);
    else if (/^-{3,}$/.test(line.trim())) out.push(<hr key={idx} />);
    else out.push(<p key={idx}>{inline(line, idx)}</p>);
  });
  flush();
  return <div className="reply">{out}</div>;
}
