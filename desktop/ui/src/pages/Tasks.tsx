import React, { useEffect, useState } from "react";
import { Me, getJSON, postJSON, patchJSON, delJSON } from "../api";
import { BigTitle, Card, Modal, Segmented, StatCard, Spinner } from "../components/ui";
import { mdToHtml } from "../lib/md";

interface AlarmsResp {
  alarms: { dt: string; eqp_id: string; level: string; code: string; message: string }[];
  summary: { total: number; critical: number; alarm: number; warn: number };
  by_eqp: [string, number][];
}
interface Task { id: number; title: string; detail: string; kind: string; status: string; due_at: string | null }
interface Report { generated_at: string; hours: number; markdown: string; alarms: { total_open: number; critical: number } }

const LEVEL_TONE: Record<string, string> = {
  CRITICAL: "bg-[#FF453A]/15 text-[#FF453A]", ALARM: "bg-[#FF9500]/15 text-[#FF9500]",
  WARN: "bg-[#FFD60A]/20 text-[#B58A00]",
};

export default function Tasks({ me }: { me: Me }) {
  const [data, setData] = useState<AlarmsResp | null>(null);
  const [hours, setHours] = useState(24 * 7);
  const [loading, setLoading] = useState(true);

  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskFilter, setTaskFilter] = useState<"all" | "open" | "done">("all");
  const [newTitle, setNewTitle] = useState("");
  const [newDue, setNewDue] = useState("");

  const [report, setReport] = useState<Report | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportHours, setReportHours] = useState(12);

  const loadAlarms = async (h: number) => {
    setLoading(true);
    try { setData(await getJSON<AlarmsResp>(`/api/tasks/alarms?hours=${h}`)); }
    catch { setData(null); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadAlarms(hours); }, [hours]);

  const loadTasks = async () => {
    const r = await getJSON<{ tasks: Task[] }>("/api/tasks/list");
    setTasks(r.tasks);
  };
  useEffect(() => { loadTasks(); }, []);

  const addTask = async () => {
    if (!newTitle.trim()) return;
    await postJSON("/api/tasks/list", { title: newTitle.trim(), due_at: newDue || null });
    setNewTitle(""); setNewDue("");
    loadTasks();
  };
  const toggleTask = async (t: Task) => {
    await patchJSON(`/api/tasks/list/${t.id}`, { status: t.status === "done" ? "open" : "done" });
    loadTasks();
  };
  const delTask = async (id: number) => {
    await delJSON(`/api/tasks/list/${id}`);
    loadTasks();
  };
  const genReport = async () => {
    setReportBusy(true);
    try { setReport(await getJSON<Report>(`/api/tasks/shift-report?hours=${reportHours}`)); }
    finally { setReportBusy(false); }
  };

  const maxEqp = data ? Math.max(1, ...data.by_eqp.map(x => x[1])) : 1;
  const filtered = tasks.filter(t => taskFilter === "all" || t.status === taskFilter);
  const overdue = (t: Task) => t.status === "open" && !!t.due_at && t.due_at < new Date().toISOString().slice(0, 10);

  return (
    <div className="h-full overflow-y-auto px-6 pt-[46px] pb-6">
      <BigTitle sub="告警值守 · 我的任务 · 交班报告">任务中心</BigTitle>

      {/* ── 告警值守 ── */}
      <div className="flex items-center gap-2 mb-3">
        <span className="ios-section-title !pb-0">告警值守</span>
        {[24, 24 * 3, 24 * 7].map(h => (
          <button key={h} onClick={() => setHours(h)}
            className={`px-3 py-1 rounded-[9px] text-[12.5px] font-medium transition-colors
              ${hours === h ? "bg-[#0A84FF] text-white" : "ios-btn-ghost"}`}>
            {h === 24 ? "近 24 小时" : `近 ${h / 24} 天`}
          </button>
        ))}
        <button className="ios-btn-ghost py-1" onClick={() => loadAlarms(hours)}>刷新</button>
      </div>

      {loading && !data ? <Spinner text="加载告警数据…" /> : data && (
        <>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <StatCard value={data.summary.total} label="未处理总数" tone={data.summary.total ? "red" : "green"} />
            <StatCard value={data.summary.critical} label="CRITICAL" tone="red" />
            <StatCard value={data.summary.alarm} label="ALARM" tone="orange" />
            <StatCard value={data.summary.warn} label="WARN" tone="neutral" />
          </div>
          <div className="grid grid-cols-2 gap-4 mb-5">
            <Card>
              <div className="text-[13px] font-semibold mb-2.5">机台分布</div>
              <div className="space-y-2.5">
                {data.by_eqp.map(([eqp, n]) => (
                  <div key={eqp}>
                    <div className="flex justify-between text-[12.5px] mb-1">
                      <span className="font-medium">{eqp}</span><span className="text-ios-label2">{n} 条</span>
                    </div>
                    <div className="h-2 rounded-full bg-black/[.06] dark:bg-white/[.08]">
                      <div className="h-full rounded-full bg-[#FF453A]" style={{ width: `${(n / maxEqp) * 100}%` }} />
                    </div>
                  </div>
                ))}
                {!data.by_eqp.length && <div className="text-[13px] text-ios-label2 py-2">暂无告警 🎉</div>}
              </div>
            </Card>
            <Card className="p-0 max-h-[300px] overflow-y-auto">
              {data.alarms.map((a, i) => (
                <div key={i} className="flex items-center gap-2.5 px-4 py-2 border-b border-black/5 dark:border-white/5 last:border-0">
                  <span className={`px-1.5 py-0.5 rounded text-[10.5px] font-bold ${LEVEL_TONE[a.level] || ""}`}>{a.level}</span>
                  <span className="font-medium text-[12.5px] w-[76px]">{a.eqp_id}</span>
                  <span className="flex-1 text-[12.5px] truncate" title={a.message}>{a.message}</span>
                  <span className="text-[11px] text-ios-label2">{a.dt}</span>
                </div>
              ))}
              {!data.alarms.length && <div className="px-4 py-6 text-center text-ios-label2 text-[13px]">当前窗口内没有未处理告警</div>}
            </Card>
          </div>
        </>
      )}

      {/* ── 我的任务 ── */}
      <div className="flex items-center gap-2 mb-3 mt-2">
        <span className="ios-section-title !pb-0">我的任务</span>
        <Segmented value={taskFilter} onChange={setTaskFilter}
          options={[{ value: "all", label: "全部" }, { value: "open", label: "未完成" }, { value: "done", label: "已完成" }]} />
      </div>
      <Card className="mb-5">
        <div className="flex gap-2 mb-3">
          <input className="ios-input flex-1" placeholder="新任务标题…" value={newTitle}
            onChange={e => setNewTitle(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") addTask(); }} />
          <input className="ios-input w-[150px]" type="date" value={newDue} onChange={e => setNewDue(e.target.value)} />
          <button className="ios-btn-primary px-4" onClick={addTask} disabled={!newTitle.trim()}>添加</button>
        </div>
        <div className="divide-y divide-black/5 dark:divide-white/5">
          {filtered.map(t => (
            <div key={t.id} className="flex items-center gap-2.5 py-2">
              <input type="checkbox" checked={t.status === "done"} onChange={() => toggleTask(t)}
                className="w-4 h-4 accent-[#30D158]" />
              <span className={`flex-1 text-[13.5px] ${t.status === "done" ? "line-through text-ios-label2" : ""} ${overdue(t) ? "text-[#FF453A] font-medium" : ""}`}>
                {t.title}
                {overdue(t) && <span className="ml-2 text-[11px]">（已逾期）</span>}
              </span>
              {t.due_at && <span className="text-[11px] text-ios-label2">截止 {t.due_at}</span>}
              <button className="text-[12px] text-ios-label2 hover:text-[#FF453A]" onClick={() => delTask(t.id)}>删除</button>
            </div>
          ))}
          {!filtered.length && <div className="py-3 text-[13px] text-ios-label2">没有任务 — 添加一个吧</div>}
        </div>
      </Card>

      {/* ── 交班报告 ── */}
      <div className="flex items-center gap-2 mb-3">
        <span className="ios-section-title !pb-0">交班报告</span>
        <Segmented value={String(reportHours)} onChange={v => setReportHours(Number(v))}
          options={[{ value: "8", label: "8 小时" }, { value: "12", label: "12 小时" }, { value: "24", label: "24 小时" }]} />
        <button className="ios-btn-primary py-1.5 px-4 text-[13px]" disabled={reportBusy} onClick={genReport}>
          {reportBusy ? "生成中…" : "生成交班报告"}
        </button>
      </div>
      {reportBusy && <Spinner text="聚合告警/良率/WIP 数据…" />}

      {report && (
        <Modal title={`交班报告（近 ${report.hours} 小时）`} onClose={() => setReport(null)} wide>
          <div className="text-[12px] text-ios-label2 mb-2">
            生成于 {report.generated_at} · 未处理告警 {report.alarms.total_open} 条（CRITICAL {report.alarms.critical}）
          </div>
          <div className="bg-black/[.03] dark:bg-white/[.05] rounded-[10px] p-4 max-h-[46vh] overflow-auto
            [&_h1]:text-[17px] [&_h1]:font-bold [&_h2]:text-[14.5px] [&_h2]:font-bold [&_h2]:mt-3
            [&_li]:ml-4 [&_ul]:list-disc [&_p]:my-1.5"
            dangerouslySetInnerHTML={{ __html: mdToHtml(report.markdown) }} />
          <div className="flex gap-2 mt-3">
            <button className="ios-btn-primary" onClick={() => navigator.clipboard.writeText(report.markdown)}>复制全文</button>
            <button className="ios-btn-ghost" onClick={() => {
              const blob = new Blob([report.markdown], { type: "text/markdown;charset=utf-8" });
              const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
              a.download = `交班报告_${report.generated_at.slice(0, 10)}.md`; a.click();
            }}>导出 .md</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
