import React, { useEffect, useRef, useState } from "react";
import { Me, ChatMsg, SessionMeta, getJSON, postJSON, patchJSON, delJSON } from "../api";
import { Modal } from "../components/ui";

const CHIPS = ["最近未处理的告警有哪些", "射频功率漂移怎么处理", "ETCH 区几台机台是 DOWN 的", "P1234 最近一周良率"];

export default function Chat({ me, initialSession }: { me: Me; initialSession?: string | null }) {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [generating, setGenerating] = useState(false);
  const [srcModal, setSrcModal] = useState<{ title: string; text: string } | null>(null);
  const [search, setSearch] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const firstRun = useRef(true);

  const refresh = async () => {
    const r = await getJSON<{ sessions: SessionMeta[] }>("/api/sessions");
    const mapped = r.sessions.map(s => {
      const old = sessions.find(o => o.id === s.id);
      return { ...s, _messages: old?.["messages"], _hasMore: old?.["hasMore"], _oldest: old?.["oldestId"] };
    });
    setSessions(mapped as any);
  };
  // 从侧栏「最近会话」进入时，先拉会话列表再打开目标会话，避免列表覆盖已加载的消息
  useEffect(() => {
    refresh().then(() => initialSession ? openSession(initialSession) : undefined).catch(() => {});
  }, []);
  useEffect(() => {
    if (firstRun.current) { firstRun.current = false; return; }
    if (initialSession) openSession(initialSession).catch(() => {});
  }, [initialSession]);

  const openSession = async (id: string, beforeId?: number) => {
    if (generating) return;
    if (!beforeId) setActiveId(id);
    const qs = beforeId ? `?before_id=${beforeId}&limit=50` : "?limit=50";
    const page = await getJSON<{ messages: any[]; has_more: boolean }>(`/api/sessions/${id}/messages${qs}`);
    const mapped: ChatMsg[] = page.messages.map((m: any) => m.role === "user"
      ? { role: "user" as const, id: m.id, text: m.content, ts: m.created_at }
      : { role: "assistant" as const, id: m.id, type: (m.type as any) || (m.sql_text ? "sql" : "kb"),
          text: m.type === "sql" || m.sql_text ? m.sql_text : m.content,
          sources: m.sources || [], sql: m.sql_text, columns: m.columns || [], rows: m.rows || [],
          row_count: m.row_count || 0, rating: m.rating, ts: m.created_at });
    setSessions(prev => prev.map(s => s.id === id ? {
      ...s,
      messages: beforeId ? [...mapped, ...(s.messages || [])] : mapped,
      hasMore: page.has_more, oldestId: mapped.length ? mapped[0].id : null,
    } as any : s));
    setActiveId(id);
  };

  const loadEarlier = async () => {
    const s: any = sessions.find(x => x.id === activeId);
    if (!s || !s.hasMore || !s.oldestId || generating) return;
    const first = s.messages?.[0]?.id;
    if (!first) return;
    await openSession(s.id, first);
  };

  const delSession = async (id: string) => {
    if (!confirm("确认删除该会话？")) return;
    await delJSON(`/api/sessions/${id}`);
    setSessions(prev => prev.filter(s => s.id !== id));
    if (activeId === id) { setActiveId(null); setMessages([]); }
  };

  const rename = async (id: string, old: string) => {
    const t = prompt("新标题：", old || "");
    if (!t?.trim()) return;
    await patchJSON(`/api/sessions/${id}`, { title: t.trim() });
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title: t.trim() } : s));
  };

  const history = () => {
    const s: any = sessions.find(x => x.id === activeId);
    return (s?.messages || []).slice(-8).map((m: ChatMsg) => ({
      role: m.role, content: m.type === "sql" ? "查询: " + m.text : m.text,
    }));
  };

  const send = async () => {
    const q = input.trim();
    if (!q || generating) return;
    setInput("");
    let sid = activeId;
    const userMsg: ChatMsg = { role: "user", text: q, ts: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) };
    const am: ChatMsg = { role: "assistant", text: "", type: "kb", sources: [], streaming: true };
    setMessages(prev => [...prev, userMsg, am]);
    setGenerating(true);
    const abort = new AbortController();
    abortRef.current = abort;
    try {
      const resp = await fetch("/api/chat/stream", {
        method: "POST", signal: abort.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, session_id: sid, history: history().slice(0, -2) }),
      });
      const reader = resp.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      const handle = (ev: string, data: any) => {
        setMessages(prev => {
          const arr = [...prev];
          const m = arr[arr.length - 1];
          if (ev === "meta") { m.type = data.type; if (data.session_id) sid = data.session_id; }
          else if (ev === "delta") m.text += data.text;
          else if (ev === "done") { m.sources = data.sources || []; m.id = data.message_id; m.streaming = false; }
          else if (ev === "result") { Object.assign(m, { type: "sql", text: data.sql, sql: data.sql, columns: data.columns, rows: data.rows, row_count: data.row_count, id: data.message_id, streaming: false }); }
          else if (ev === "error") { m.error = true; m.text = data.message || "未知错误"; m.streaming = false; }
          return arr;
        });
      };
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i: number;
        while ((i = buf.indexOf("\n\n")) >= 0) {
          const raw = buf.slice(0, i); buf = buf.slice(i + 2);
          let ev = "message", data = "";
          raw.split("\n").forEach(line => {
            if (line.startsWith("event:")) ev = line.slice(6).trim();
            else if (line.startsWith("data:")) data += line.slice(5).trim();
          });
          if (data) { try { handle(ev, JSON.parse(data)); } catch { /* ignore */ } }
        }
      }
      setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, streaming: false, ts: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) } : m));
      refresh();
    } catch (e: any) {
      setMessages(prev => { const arr = [...prev]; const m = arr[arr.length - 1];
        m.streaming = false;
        if (e.name === "AbortError") { m.text += "\n\n（已停止）"; }
        else { m.error = true; m.text = "请求失败: " + e.message; }
        return arr; });
    } finally {
      setGenerating(false); abortRef.current = null;
    }
  };

  const stop = () => abortRef.current?.abort();
  const rate = async (id: number | null | undefined, val: string) => {
    if (!id) return;
    await postJSON("/api/feedback", { message_id: id, rating: val });
    setMessages(prev => prev.map(m => m.id === id ? { ...m, rating: val } : m));
  };

  const cur: any = sessions.find(s => s.id === activeId);
  const msgList: ChatMsg[] = cur?.messages || [];
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => { const el = scrollRef.current; if (el) el.scrollTop = el.scrollHeight; }, [messages.length, generating]);

  return (
    <div className="app-chat">
      {/* 会话列表 */}
      <div className="chat-col relative w-[240px] shrink-0 flex flex-col bg-black/[.02] dark:bg-white/[.03]">
        <span className="edge-divider" aria-hidden />
        <div className="px-3 pb-2">
          <input className="ios-input !py-1.5 text-[13px]" placeholder="搜索会话…" value={search}
            onChange={e => setSearch(e.target.value)} />
          <button className="ios-btn-primary w-full mt-2 py-1.5 text-[13px]"
            onClick={() => { setActiveId(null); setMessages([]); }}>＋ 新会话</button>
        </div>
        <div className="flex-1 overflow-y-auto px-2.5 pb-2 space-y-1">
          {sessions.filter(s => !search || (s.title || "").toLowerCase().includes(search.toLowerCase())).map(s => (
            <div key={s.id} onClick={() => openSession(s.id)}
              className={`group px-2.5 py-2 rounded-[10px] cursor-pointer text-[13px] transition-colors
                ${activeId === s.id ? "bg-[#0A84FF]/15 text-[#0A84FF] font-semibold" : "hover:bg-black/5 dark:hover:bg-white/10"}`}>
              <div className="truncate">{s.title}</div>
              <div className="flex justify-between text-[11px] text-ios-label2">
                <span>{s.message_count} 条</span>
                <span className="opacity-0 group-hover:opacity-100 flex gap-1.5">
                  <button onClick={e => { e.stopPropagation(); rename(s.id, s.title); }}>✎</button>
                  <button onClick={e => { e.stopPropagation(); delSession(s.id); }} className="hover:text-[#FF453A]">🗑</button>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 对话区 */}
      <div className="chat-col flex-1 min-w-0 flex flex-col">
        <div className="px-5 pb-2 header-hairline flex items-center">
          <div className="font-semibold text-[15px]">{cur?.title || "新会话"}</div>
          {cur && <button className="ml-auto text-[12px] text-ios-label2 hover:text-current"
            onClick={() => exportMd(cur)}>导出 Markdown</button>}
        </div>
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4">
          {!msgList.length && (
            <div className="h-full grid place-items-center text-center">
              <div>
                <div className="text-[42px] mb-2">💬</div>
                <div className="text-[18px] font-bold mb-1">AI 对话</div>
                <div className="text-[13px] text-ios-label2 mb-6">知识问答附引用来源 · 数据查询只读安全</div>
                <div className="grid grid-cols-2 gap-2 w-full max-w-[440px] min-w-0">
                  {CHIPS.map(c => (
                    <button key={c} onClick={() => { setInput(c); setTimeout(send, 0); }}
                      className="ios-card px-3 py-2.5 text-[13px] text-left transition-colors">{c}</button>
                  ))}
                </div>
              </div>
            </div>
          )}
          {cur?.hasMore && msgList.length > 0 && (
            <div className="text-center mb-3">
              <button className="ios-btn-ghost text-[12px] py-1" onClick={loadEarlier}>加载更早消息</button>
            </div>
          )}
          {msgList.map((m, i) => <Message key={i} m={m} onRate={rate}
            onSrc={(t, x) => setSrcModal({ title: t, text: x })} />)}
        </div>
        <div className="px-5 pb-4">
          <div className="ios-card p-3">
            <textarea className="w-full bg-transparent outline-none resize-none text-[14px] leading-6 max-h-[120px]"
              rows={1} value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder="输入问题…（Enter 发送 / Shift+Enter 换行）" />
            <div className="flex items-center mt-1.5">
              <span className="text-[11.5px] text-ios-label2 flex-1">回答基于知识库并附引用来源 · 数据查询只读安全</span>
              {generating && <button className="ios-btn-ghost mr-2 text-[12px] py-1" onClick={stop}>■ 停止</button>}
              <button className="ios-btn-primary px-5 py-1.5 text-[13px]" disabled={generating || !input.trim()}
                onClick={send}>发送</button>
            </div>
          </div>
        </div>
        {srcModal && <Modal title={srcModal.title} onClose={() => setSrcModal(null)} wide>
          <pre className="selectable whitespace-pre-wrap text-[13.5px] leading-6 bg-black/[.03] dark:bg-white/[.05] rounded-[10px] p-3.5">{srcModal.text}</pre>
        </Modal>
        }
      </div>
    </div>
  );
}

function esc(s: any) {
  const map: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
  return (s ?? "").toString().replace(/[&<>"]/g, (c: string) => map[c]);
}

function mdToHtml(src: string) {
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
    if (t === "") { flush(); if (ul) { out += "</ul>"; ul = false; } continue; }
    para.push(ln);
  }
  flush(); if (ul) out += "</ul>";
  return out;
}

function Message({ m, onRate, onSrc }: { m: ChatMsg; onRate: (id: any, v: string) => void; onSrc: (t: string, x: string) => void }) {
  if (m.role === "user")
    return <div className="flex justify-end mb-3"><div className="selectable bg-[#0A84FF] text-white max-w-[72%] px-4 py-2.5
      rounded-[16px] rounded-br-[4px] text-[14px] leading-6 whitespace-pre-wrap">{m.text}</div></div>;
  return (
    <div className="mb-4">
      <div className={`selectable ios-card px-4 py-3.5 text-[14px] leading-6 ${m.error ? "border-[#FF453A]/40 bg-[#FF453A]/5" : ""}`}>
        {m.type === "sql" ? (
          <>
            <pre className="bg-[#10161F] text-[#D8E2EF] rounded-[9px] p-3 text-[12.5px] overflow-x-auto">{esc(m.sql || m.text)}</pre>
            <ResultTable cols={m.columns || []} rows={m.rows || []} />
            <div className="meta text-[11.5px] text-ios-label2 mt-2">返回 {m.row_count ?? 0} 行 · 只读 SELECT {m.ts ? "· " + m.ts : ""}</div>
          </>
        ) : (
          <>
            <div className="prose-sm" dangerouslySetInnerHTML={{ __html: mdToHtml(m.text) }} />
            {m.streaming && <span className="inline-block w-2 h-4 bg-[#FF9500] rounded-[2px] animate-pulse ml-0.5 align-middle" />}
            {!!m.sources?.length && (
              <div className="mt-2.5 pt-2 border-t border-dashed border-black/10 dark:border-white/10 flex flex-wrap gap-1.5">
                {m.sources.map(s => (
                  <button key={s.idx} onClick={() => onSrc(`[${s.idx}] ${s.source} (相似度 ${s.score})`, s.text || s.excerpt || "")}
                    className="text-[11.5px] px-2 py-0.5 rounded-[7px] bg-black/[.04] dark:bg-white/[.06] hover:bg-black/10 transition-colors"
                    title="点击查看片段全文">
                    <b className="text-[#FF9500]">[{s.idx}]</b> {s.source} · {s.score}
                  </button>
                ))}
              </div>
            )}
            <div className="meta text-[11.5px] text-ios-label2 mt-2 flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-full bg-[#FF9500]/15 text-[#FF9500] text-[11px] font-semibold">知识问答</span>
              <span>{m.ts}</span>
              <button className="hover:text-current" onClick={() => navigator.clipboard.writeText(m.text)}>复制</button>
              {m.id && <>
                <button onClick={() => onRate(m.id, m.rating === "up" ? "none" : "up")}
                  className={m.rating === "up" ? "text-[#30D158]" : ""}>👍</button>
                <button onClick={() => onRate(m.id, m.rating === "down" ? "none" : "down")}
                  className={m.rating === "down" ? "text-[#FF453A]" : ""}>👎</button>
              </>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ResultTable({ cols, rows }: { cols: string[]; rows: any[][] }) {
  if (!cols.length) return null;
  return (
    <div className="selectable overflow-x-auto mt-2">
      <table className="w-full text-[12.8px] border-collapse">
        <thead><tr>{cols.map(c => <th key={c} className="bg-[#FF9500] text-white text-left px-2.5 py-1.5 font-semibold">{c}</th>)}</tr></thead>
        <tbody>{rows.slice(0, 50).map((r, i) => (
          <tr key={i} className={i % 2 ? "bg-[#FF9500]/[.05]" : ""}>
            {r.map((v, j) => <td key={j} className="border border-black/10 dark:border-white/10 px-2.5 py-1">{String(v ?? "")}</td>)}
          </tr>))}
        </tbody>
      </table>
      {rows.length > 50 && <div className="text-[11.5px] text-ios-label2 mt-1">仅显示前 50 行 / 共 {rows.length} 行</div>}
    </div>
  );
}

function exportMd(s: any) {
  const lines: string[] = [`# ${s.title} (导出于 ${new Date().toLocaleString("zh-CN")})`, ""];
  (s.messages || []).forEach((m: any) => {
    if (m.role === "user") lines.push(`**🙋 用户：** ${m.text}`, "");
    else if (m.type === "sql") lines.push(`**🤖 Fab Bot（数据查询）：**`, "```sql", m.sql || m.text, "```", `返回 ${m.row_count ?? 0} 行`, "");
    else if (m.error) lines.push(`**🤖 Fab Bot（错误）：** ${m.text}`, "");
    else { lines.push(`**🤖 Fab Bot（知识问答）：**`, m.text, ""); if (m.sources?.length) lines.push("来源: " + m.sources.map((x: any) => `[${x.idx}] ${x.source}`).join(" · "), ""); }
  });
  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `${(s.title || "会话").replace(/[\\/:*?"<>|]/g, "_")}.md`; a.click();
}
