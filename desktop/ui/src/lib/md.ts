/* Markdown → HTML 渲染 (轻量: 代码块/行内码/加粗/列表/标题), 全应用共享 */

export function esc(s: any) {
  const map: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
  return (s ?? "").toString().replace(/[&<>"]/g, (c: string) => map[c]);
}

export function mdToHtml(src: string) {
  const blocks: string[] = [];
  let s = (src || "").replace(/```(\w*)\n?([\s\S]*?)```/g, (_m, _l, c) => {
    blocks.push(`<pre class="bg-[#10161F] text-[#D8E2EF] rounded-[9px] p-3 text-[12.5px] overflow-x-auto"><code>${esc(c.trimEnd())}</code></pre>`);
    return `\u0000${blocks.length - 1}\u0000`;
  });
  s = esc(s).replace(/`([^`\n]+)`/g, '<code class="bg-black/5 dark:bg-white/10 rounded px-1">$1</code>')
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  const lines = s.split("\n");
  let out = "", ul = false, para: string[] = [];
  const flush = () => { if (para.length) { out += "<p>" + para.join("<br>") + "</p>"; para = []; } };
  for (const ln of lines) {
    const t = ln.trim();
    if (/^\u0000\d+\u0000$/.test(t)) { flush(); if (ul) { out += "</ul>"; ul = false; } out += blocks[+t.slice(1, -1)]; continue; }
    if (/^- /.test(ln)) { flush(); if (!ul) { out += "<ul class='list-disc pl-5'>"; ul = true; } out += `<li>${ln.slice(2)}</li>`; continue; }
    if (/^#{1,4} /.test(t)) {
      flush(); if (ul) { out += "</ul>"; ul = false; }
      out += `<div style="font-weight:700;margin:10px 0 4px">${t.replace(/^#+ /, "")}</div>`;
      continue;
    }
    if (t === "") { flush(); if (ul) { out += "</ul>"; ul = false; } continue; }
    para.push(ln);
  }
  flush(); if (ul) out += "</ul>";
  return out;
}
