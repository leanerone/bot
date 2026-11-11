import React, { useEffect, useState } from "react";
import { Me, Health, getJSON, SessionMeta } from "../api";
import { Card, BigTitle, StatCard } from "../components/ui";

export default function Home({ me, health, go }: { me: Me; health: Health | null; go: (v: any) => void }) {
  const [summary, setSummary] = useState<any>(null);
  const [sessions, setSessions] = useState<SessionMeta[]>([]);

  useEffect(() => {
    getJSON("/api/tasks/summary").then(setSummary).catch(() => setSummary(null));
    getJSON<{ sessions: SessionMeta[] }>("/api/sessions").then(r => setSessions(r.sessions)).catch(() => {});
  }, []);

  const quick: { icon: string; label: string; desc: string; view: string }[] = [
    { icon: "💬", label: "开始对话", desc: "问 SOP、处置经验", view: "chat" },
    { icon: "📊", label: "查生产数据", desc: "告警 / WIP / 良率", view: "data" },
    { icon: "📚", label: "知识库", desc: "导入与治理文档", view: "kb" },
    { icon: "🛎️", label: "告警值守", desc: "未处理告警面板", view: "tasks" },
  ];

  return (
    <div className="h-full overflow-y-auto px-6 pt-[46px] pb-6">
      <BigTitle sub={`你好，${me.display_name || me.username} · ${new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric", weekday: "long" })}`}>
        工作台
      </BigTitle>

      <div className="grid grid-cols-4 gap-3 mb-5">
        <StatCard value={summary ? summary.alarms.total : "–"} label="未处理告警" tone={summary && summary.alarms.total > 0 ? "red" : "green"} />
        <StatCard value={summary ? summary.alarms.critical : "–"} label="其中 CRITICAL" tone="red" />
        <StatCard value={health ? health.kb_chunks : "–"} label="知识库片段" tone="blue" />
        <StatCard value={sessions.length} label="我的会话" tone="orange" />
      </div>

      <div className="ios-section-title">快速开始</div>
      <div className="grid grid-cols-2 gap-3 mb-5">
        {quick.map(q => (
          <button key={q.label} onClick={() => go(q.view)}
            className="ios-card p-4 text-left hover:scale-[1.01] active:scale-[.99] transition-transform duration-200 ease-ios">
            <div className="flex items-center gap-3">
              <span className="text-[24px]">{q.icon}</span>
              <div>
                <div className="font-semibold text-[15px]">{q.label}</div>
                <div className="text-[12px] text-ios-label2">{q.desc}</div>
              </div>
              <span className="ml-auto text-ios-label2">›</span>
            </div>
          </button>
        ))}
      </div>

      <div className="ios-section-title">最近会话</div>
      <Card className="divide-y divide-black/5 dark:divide-white/5">
        {sessions.slice(0, 5).map(s => (
          <div key={s.id} className="py-2.5 flex items-center gap-3 cursor-pointer hover:bg-black/[.03] dark:hover:bg-white/[.04] -mx-2 px-2 rounded-[10px]"
            onClick={() => go("chat")}>
            <span className="text-[15px]">💬</span>
            <span className="flex-1 text-[14px] truncate">{s.title}</span>
            <span className="text-[11.5px] text-ios-label2">{s.message_count} 条 · {fmt(s.updated_at)}</span>
          </div>
        ))}
        {!sessions.length && <div className="py-3 text-[13px] text-ios-label2">还没有会话 — 从「开始对话」发起第一条提问</div>}
      </Card>
    </div>
  );
}

function fmt(ts: string) { return ts ? ts.slice(5, 16).replace("T", " ") : ""; }
