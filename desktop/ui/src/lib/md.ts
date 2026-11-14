/* Markdown → HTML 渲染 (轻量: 代码块/行内码/加粗/列表/标题), 全应用共享
   A2: 流式容错 (未闭合 ``` fence 按已闭合部分渲染) + 代码块复制按钮 */

export function esc(s: any) {
  const map: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
  return (s ?? "").toString().replace(/[&<>"]/g, (c: string) => map[c]);
}

function codeBlockHtml(code: string, lang: string) {
  const label = lang ? `<span class="code-lang">${esc(lang)}</span>` : "";
  return `<div class="code-block"><div class="code-head">${label}`
    + `<button class="code-copy-btn" title="复制代码">复制</button></div>`
    + `<pre class="bg-[#10161F] text-[#D8E2EF] rounded-b-[9px] p-3 text-[12.5px] overflow-x-auto"><code>${esc(code.trimEnd())}</code></pre></div>`;
}

export function mdToHtml(src: string, streaming = false) {
  const blocks: string[] = [];
  // 流式容错: 末尾未闭合 fence 视为代码块渲染, 防整段闪烁为纯文本
  let s0 = src || "";
  const fenceCount = (s0.match(/```/g) || []).length;
  if (streaming && fenceCount % 2 === 1) { s0 += "\n```"; }
  let s = s0.replace(/```(\w*)\n?([\s\S]*?)```/g, (_m, l: string, c: string) => {
    blocks.push(codeBlockHtml(c, l));
    return `\u0000${blocks.length - 1}\u0000`;
  });
  s = esc(s).replace(/`([^`\n]+)`/g, '<code class="bg-black/5 dark:bg-white/10 rounded px-1">$1</code>')
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  // A3: [1] 引用上标 (渲染层高亮, 点击行为由容器事件代理)
  s = s.replace(/\[(\d{1,2})\](?!\()/g, '<sup class="cite-mark">[$1]</sup>');
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
