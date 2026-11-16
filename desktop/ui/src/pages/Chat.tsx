import React, { useEffect, useRef, useState } from "react";
import { Me, ChatMsg, SessionMeta, getJSON, postJSON, patchJSON, delJSON } from "../api";
import { Modal, Switch } from "../components/ui";

const CHIPS = ["最近未处理的告警有哪些", "射频功率漂移怎么处理", "ETCH 区几台机台是 DOWN 的", "P1234 最近一周良率"];

/* v4.4 重构: 当前会话消息统一存 messages 单一状态 (修复原"会话态/流式态"双源脱节),
   sessions 仅作侧栏列表; A1 流式缓冲+滚动跟随 / A2 代码复制 / A3 引用上标+Notes 回链 /
   A4 骨架屏与动效 / D3 Agent 模式步骤条 */

export default function Chat({ me, initialSession }: { me: Me; initialSession?: string | null }) {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [oldestId, setOldestId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [generating, setGenerating] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const [steps, setSteps] = useState<{ tool: string; ok: boolean; summary: string }[]>([]);
  const [loadingSession, setLoadingSession] = useState(false);
  const [srcModal, setSrcModal] = useState<{ title: string; text: string; link?: string } | null>(null);
  const [search, setSearch] = useState("");
  const [follow, setFollow] = useState(true);        // A1: 滚动跟随 (用户上滚即停)
  const abortRef = useRef<AbortController | null>(null);
  const firstRun = useRef(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeIdRef = useRef<string | null>(null);
  useEffect(() => { activeIdRef.current = activeId; }, [activeId]);

  const refresh = async () => {
    const r = await getJSON<{ sessions: SessionMeta[] }>("/api/sessions");
    setSessions(r.sessions);
  };

  useEffect(() => {
    refresh().then(() => initialSession ? openSession(initialSession) : undefined).catch(() => {});
  }, []);
  useEffect(() => {
    if (firstRun.current) { firstRun.current = false; return; }
    if (initialSession) openSession(initialSession).catch(() => {});
  }, [initialSession]);

  const openSession = async (id: string, beforeId?: number) => {
    if (generating) return;
    if (!beforeId) { setActiveId(id); setLoadingSession(true); }
    const qs = beforeId ? `?before_id=${beforeId}&limit=50` : "?limit=50";
    const page = await getJSON<{ messages: any[]; has_more: boolean }>(`/api/sessions/${id}/messages${qs}`);
    const mapped: ChatMsg[] = page.messages.map((m: any) => m.role === "user"
      ? { role: "user" as const, id: m.id, text: m.content, ts: m.created_at }
      : { role: "assistant" as const, id: m.id, type: (m.type as any) || (m.sql_text ? "sql" : "kb"),
          text: m.type === "sql" || m.sql_text ? m.sql_text : m.content,
          sources: m.sources || [], sql: m.sql_text, columns: m.columns || [], rows: m.rows || [],
          row_count: m.row_count || 0, rating: m.rating, ts: m.created_at });
    if (beforeId) {
      setMessages(prev => [...mapped, ...prev]);
    } else {
      setMessages(mapped);
    }
    setHasMore(page.has_more);
    const firstId = mapped.length ? (mapped[0].id ?? null) : null;
    setOldestId(beforeId ? (firstId ?? oldestIdRef.current) : firstId);
    setActiveId(id);
    setSteps([]);
    setLoadingSession(false);
    setFollow(true);
  };
  const oldestIdRef = useRef<number | null>(null);
  useEffect(() => { oldestIdRef.current = oldestId; }, [oldestId]);

  const loadEarlier = async () => {
    if (!hasMore || !oldestId || generating) return;
    await openSession(activeIdRef.current!, oldestId);
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

  const history = () => messages.slice(-8).map((m: ChatMsg) => ({
    role: m.role, content: m.type === "sql" ? "查询: " + m.text : m.text,
  }));

  // A1: 流式缓冲 —— delta 先入 ref 缓冲, 40ms 批量 flush 进 state, 避免逐 token 重渲染
  const pendRef = useRef("");
  const flushTimer = useRef<number | null>(null);
  const flushPend = () => {
    if (!pendRef.current) return;
    const add = pendRef.current;
    pendRef.current = "";
    setMessages(prev => {
      const arr = [...prev];
      const m = arr[arr.length - 1];
      if (m?.streaming) arr[arr.length - 1] = { ...m, text: m.text + add };
      return arr;
    });
  };
  const pushDelta = (text: string) => {
    pendRef.current += text;
    if (flushTimer.current == null) {
      flushTimer.current = window.setTimeout(() => {
        flushTimer.current = null; flushPend();
      }, 40);
    }
  };
  useEffect(() => () => { if (flushTimer.current != null) window.clearTimeout(flushTimer.current); }, []);

  const send = async (retryQ?: string) => {
    const q = (retryQ ?? input).trim();
    if (!q || generating) return;
    if (!retryQ) setInput("");
    const ts = () => new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    const userMsg: ChatMsg = { role: "user", text: q, ts: ts() };
    const am: ChatMsg = { role: "assistant", text: "", type: "kb", sources: [], streaming: true };
    // C7: 重试时移除上一轮失败的提问+回答, 再重发同一问题
    setMessages(prev => [...(retryQ ? prev.slice(0, -2) : prev), userMsg, am]);
    setSteps([]);
    setFollow(true);
    setGenerating(true);
    const abort = new AbortController();
    abortRef.current = abort;
    const url = agentMode ? "/api/agent/chat/stream" : "/api/chat/stream";
    try {
      const resp = await fetch(url, {
        method: "POST", signal: abort.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, session_id: activeIdRef.current, history: history().slice(0, -2) }),
      });
      const reader = resp.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let sid: string | null = activeIdRef.current;
      const handle = (ev: string, data: any) => {
        if (ev === "agent_step") { setSteps(prev => [...prev, data]); return; }
        setMessages(prev => {
          const arr = [...prev];
          const last = arr[arr.length - 1];
          if (!last) return arr;
          if (ev === "meta") { if (data.session_id) sid = data.session_id; }
          else if (ev === "done") {
            flushPend();
            arr[arr.length - 1] = { ...last, sources: data.sources || [], id: data.message_id, streaming: false };
          }
          else if (ev === "result") {
            flushPend();
            arr[arr.length - 1] = { ...last, type: "sql", text: data.sql, sql: data.sql,
              columns: data.columns, rows: data.rows, row_count: data.row_count, id: data.message_id, streaming: false };
          }
          else if (ev === "error") {
            arr[arr.length - 1] = { ...last, error: true, text: data.message || "未知错误", streaming: false };
          }
          return arr;
        });
        if (ev === "delta") pushDelta(data.text);
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
          if (data) {
            try { handle(ev, JSON.parse(data)); }
            catch (err) { console.warn("SSE 事件解析失败:", data, err); }   // C7: 不静默吞错, 也不中断流
          }
        }
      }
      flushPend();
      setMessages(prev => prev.map((m, i) => i === prev.length - 1 ? { ...m, streaming: false, ts: ts() } : m));
      if (sid && !activeIdRef.current) setActiveId(sid);
      refresh();
    } catch (e: any) {
      flushPend();
      setMessages(prev => { const arr = [...prev]; const m = arr[arr.length - 1];
        if (!m) return arr;
        arr[arr.length - 1] = { ...m, streaming: false,
          text: e.name === "AbortError" ? m.text + "\n\n（已停止）" : "请求失败: " + e.message,
          error: e.name !== "AbortError",
          retry: e.name !== "AbortError" ? q : undefined };   // C7: 失败消息可重试
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

  // A1: 滚动跟随
  useEffect(() => {
    const el = scrollRef.current;
    if (el && follow) el.scrollTop = el.scrollHeight;
  }, [messages, steps, generating, follow]);
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    if (!atBottom && generating) setFollow(false);
    if (atBottom && !follow) setFollow(true);
  };

  // A3: 引用上标/代码复制 (事件代理)
  const onBodyClick = (e: React.MouseEvent) => {
    const el = (e.target as HTMLElement).closest(".code-copy-btn") as HTMLElement | null;
    if (el) {
      const code = el.closest(".code-block")?.querySelector("code")?.textContent || "";
      navigator.clipboard.writeText(code);
      el.textContent = "✓ 已复制";
      setTimeout(() => { el.textContent = "复制"; }, 1200);
      return;
    }
    const cite = (e.target as HTMLElement).closest(".cite-mark") as HTMLElement | null;
    if (!cite) return;
    const idx = parseInt(cite.textContent?.replace(/\D/g, "") || "0", 10);
    const s: any = messages.flatMap(m => m.sources || []).find(x => x.idx === idx);
    if (s) setSrcModal({ title: `[${s.idx}] ${s.source} (相似度 ${s.score})`, text: s.text || s.excerpt || "", link: s.link });
  };

  const cur = sessions.find(s => s.id === activeId);
  const thinking = generating && !messages[messages.length - 1]?.text;

  return (
    <div className="app-chat">
      {/* 会话列表 */}
      <div className="chat-col relative w-[240px] shrink-0 flex flex-col bg-black/[.02] dark:bg-white/[.03]">
        <span className="edge-divider" aria-hidden />
        <div className="px-3 pb-2">
          <input className="ios-input !py-1.5 text-[13px]" placeholder="搜索会话…" value={search}
            onChange={e => setSearch(e.target.value)} />
          <button className="ios-btn-primary w-full mt-2 py-1.5 text-[13px]"
            onClick={() => { setActiveId(null); setMessages([]); setSteps([]); }}>＋ 新会话</button>
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
            onClick={() => exportMd(cur, messages)}>导出 Markdown</button>}
        </div>
        <div ref={scrollRef} onScroll={onScroll} onClick={onBodyClick}
          className="flex-1 overflow-y-auto px-6 py-4" aria-live="polite">
          {loadingSession && (
            <div className="space-y-3">{[0, 1, 2].map(i => <div key={i} className="ios-card h-16 skeleton-shimmer" />)}</div>
          )}
          {!loadingSession && !messages.length && !generating && (
            <div className="h-full grid place-items-center text-center">
              <div>
                <div className="text-[42px] mb-2">💬</div>
                <div className="text-[18px] font-bold mb-1">AI 对话</div>
                <div className="text-[13px] text-ios-label2 mb-6">知识问答附引用来源 · 数据查询只读安全 · Agent 模式多步工具</div>
                <div className="grid grid-cols-2 gap-2 w-full max-w-[440px] min-w-0">
                  {CHIPS.map(c => (
                    <button key={c} onClick={() => { setInput(c); }}
                      className="ios-card px-3 py-2.5 text-[13px] text-left transition-colors">{c}</button>
                  ))}
                </div>
              </div>
            </div>
          )}
          {hasMore && messages.length > 0 && (
            <div className="text-center mb-3">
              <button className="ios-btn-ghost text-[12px] py-1" onClick={loadEarlier}>加载更早消息</button>
            </div>
          )}
          {messages.map((m, i) => <Message key={i} m={m} steps={steps} thinking={thinking}
            onRate={rate} onRetry={q => send(q)} onSrc={(t, x, l) => setSrcModal({ title: t, text: x, link: l })} />)}
          {!follow && generating && (
            <button className="fixed-float" onClick={() => setFollow(true)}>↓ 回到底部</button>
          )}
        </div>
        <div className="px-5 pb-4">
          <div className="ios-card p-3">
            <textarea className="w-full bg-transparent outline-none resize-none text-[14px] leading-6 max-h-[120px]"
              rows={1} value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              placeholder={agentMode ? "Agent 模式: 自动多步调用知识检索/数据查询/告警值守…" : "输入问题…（Enter 发送 / Shift+Enter 换行）"} />
            <div className="flex items-center mt-1.5 gap-2">
              <span className="text-[11.5px] text-ios-label2 flex-1">回答基于知识库并附引用来源 · 数据查询只读安全</span>
              <label className="flex items-center gap-1.5 text-[12px] text-ios-label2 cursor-pointer select-none">
                <span className={agentMode ? "text-[#0A84FF] font-semibold" : ""}>🤖 Agent</span>
                <Switch checked={agentMode} onChange={setAgentMode} />
              </label>
              {generating && <button className="ios-btn-ghost mr-1 text-[12px] py-1" onClick={stop}>■ 停止</button>}
              <button className="ios-btn-primary px-5 py-1.5 text-[13px]" disabled={generating || !input.trim()}
                onClick={() => send()}>发送</button>
            </div>
          </div>
        </div>
        {srcModal && <Modal title={srcModal.title} onClose={() => setSrcModal(null)} wide>
          <pre className="selectable whitespace-pre-wrap text-[13.5px] leading-6 bg-black/[.03] dark:bg-white/[.05] rounded-[10px] p-3.5">{srcModal.text}</pre>
          {srcModal.link && (
            <a href={srcModal.link} className="ios-btn-primary inline-block mt-3 px-3 py-1.5 text-[12.5px] no-underline"
              title="唤起 Notes 客户端打开原文档">📝 在 Notes 中打开原文</a>
          )}
        </Modal>
        }
      </div>
    </div>
  );
}

import { esc, mdToHtml } from "../lib/md";

function Message({ m, steps, thinking, onRate, onRetry, onSrc }: {
  m: ChatMsg; steps: { tool: string; ok: boolean; summary: string }[]; thinking: boolean;
  onRate: (id: any, v: string) => void; onRetry: (q: string) => void; onSrc: (t: string, x: string, l?: string) => void;
}) {
  if (m.role === "user")
    return <div className="flex justify-end mb-3 msg-enter"><div className="selectable bg-[#0A84FF] text-white max-w-[72%] px-4 py-2.5
      rounded-[16px] rounded-br-[4px] text-[14px] leading-6 whitespace-pre-wrap">{m.text}</div></div>;
  return (
    <div className="mb-4 msg-enter">
      {/* Agent 步骤条 (D3): 逐工具展示中间过程 */}
      {steps.length > 0 && m.streaming && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {steps.map((s, i) => (
            <span key={i} className={`text-[11.5px] px-2 py-0.5 rounded-full
              ${s.ok ? "bg-[#30D158]/15 text-[#30D158]" : "bg-[#FF453A]/15 text-[#FF453A]"}`}>
              {s.ok ? "✓" : "✕"} {s.tool}
            </span>
          ))}
        </div>
      )}
      <div className={`selectable ios-card px-4 py-3.5 text-[14px] leading-6 ${m.error ? "border-[#FF453A]/40 bg-[#FF453A]/5" : ""}`}>
        {thinking && !m.text && !m.error && (
          <div className="typing-dots" aria-label="思考中"><i /><i /><i /></div>
        )}
        {m.type === "sql" ? (
          <>
            <pre className="bg-[#10161F] text-[#D8E2EF] rounded-[9px] p-3 text-[12.5px] overflow-x-auto">{esc(m.sql || m.text)}</pre>
            <ResultTable cols={m.columns || []} rows={m.rows || []} />
            <div className="meta text-[11.5px] text-ios-label2 mt-2">返回 {m.row_count ?? 0} 行 · 只读 SELECT {m.ts ? "· " + m.ts : ""}</div>
          </>
        ) : (
          <>
            <div className="prose-sm" dangerouslySetInnerHTML={{ __html: mdToHtml(m.text, m.streaming) }} />
            {m.streaming && m.text && <span className="inline-block w-2 h-4 bg-[#FF9500] rounded-[2px] animate-pulse ml-0.5 align-middle" />}
            {/* A3: 流式期间先给来源骨架 */}
            {m.streaming && !m.sources?.length && (
              <div className="mt-2.5 pt-2 border-t border-dashed border-black/10 dark:border-white/10 flex gap-1.5">
                {[0, 1, 2].map(i => <span key={i} className="h-5 w-28 rounded-[7px] bg-black/[.05] dark:bg-white/[.07] skeleton-shimmer" />)}
              </div>
            )}
            {!!m.sources?.length && (
              <div className="mt-2.5 pt-2 border-t border-dashed border-black/10 dark:border-white/10 flex flex-wrap gap-1.5">
                {m.sources.map(s => (
                  <button key={s.idx} onClick={() => onSrc(`[${s.idx}] ${s.source} (相似度 ${s.score})`, s.text || s.excerpt || "", s.link)}
                    className="text-[11.5px] px-2 py-0.5 rounded-[7px] bg-black/[.04] dark:bg-white/[.06] hover:bg-black/10 transition-colors"
                    title="点击查看片段全文">
                    <b className="text-[#FF9500]">[{s.idx}]</b> {s.source} · {s.score}{s.link ? " 📝" : ""}
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
        {/* C7: 失败消息提供重试 (重发同一问题) */}
        {m.error && m.retry && (
          <button className="ios-btn-ghost mt-2 px-3 py-1 text-[12px]" onClick={() => onRetry(m.retry!)}>↻ 重试</button>
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

function exportMd(s: any, msgList: ChatMsg[]) {
  const lines: string[] = [`# ${s.title} (导出于 ${new Date().toLocaleString("zh-CN")})`, ""];
  msgList.forEach((m: any) => {
    if (m.role === "user") lines.push(`**🙋 用户：** ${m.text}`, "");
    else if (m.type === "sql") lines.push(`**🤖 Fab Bot（数据查询）：**`, "```sql", m.sql || m.text, "```", `返回 ${m.row_count ?? 0} 行`, "");
    else if (m.error) lines.push(`**🤖 Fab Bot（错误）：** ${m.text}`, "");
    else { lines.push(`**🤖 Fab Bot（知识问答）：**`, m.text, ""); if (m.sources?.length) lines.push("来源: " + m.sources.map((x: any) => `[${x.idx}] ${x.source}`).join(" · "), ""); }
  });
  const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = `${(s.title || "会话").replace(/[\\/:*?"<>|]/g, "_")}.md`; a.click();
}
