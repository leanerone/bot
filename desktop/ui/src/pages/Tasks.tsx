import React, { useEffect, useState } from "react";
import { Me, getJSON } from "../api";
import { BigTitle, Card, StatCard, Spinner } from "../components/ui";

interface AlarmsResp {
  alarms: { dt: string; eqp_id: string; level: string; code: string; message: string }[];
  summary: { total: number; critical: number; alarm: number; warn: number };
  by_eqp: [string, number][];
}

const LEVEL_TONE: Record<string, string> = {
  CRITICAL: "bg-[#FF453A]/15 text-[#FF453A]", ALARM: "bg-[#FF9500]/15 text-[#FF9500]",
  WARN: "bg-[#FFD60A]/15 text-[#B58A00]",
};

export default function Tasks({ me }: { me: Me }) {
  const [data, setData] = useState<AlarmsResp | null>(null);
  const [hours, setHours] = useState(24 * 7);
  const [loading, setLoading] = useState(true);

  const load = async (h: number) => {
    setLoading(true);
    try { setData(await getJSON(`/api/tasks/alarms?hours=${h}`)); }
    catch { setData(null); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(hours); }, [hours]);

  const maxEqp = data ? Math.max(1, ...data.by_eqp.map(x => x[1])) : 1;

  return (
    <div className="h-full overflow-y-auto px-6 pt-[46px] pb-6">
      <BigTitle sub="未处理告警实时面板 —— 数据来自只读中间库">任务中心 · 告警值守</BigTitle>

      <div className="flex items-center gap-2 mb-4">
        {[24, 24 * 3, 24 * 7].map(h => (
          <button key={h} onClick={() => setHours(h)}
            className={`px-3 py-1.5 rounded-[9px] text-[13px] font-medium transition-colors
              ${hours === h ? "bg-[#0A84FF] text-white" : "ios-btn-ghost"}`}>
            {h === 24 ? "近 24 小时" : `近 ${h / 24} 天`}
          </button>
        ))}
        <button className="ios-btn-ghost py-1.5" onClick={() => load(hours)}>刷新</button>
      </div>

      {loading && !data ? <Spinner text="加载告警数据…" /> : data && (
        <>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <StatCard value={data.summary.total} label="未处理总数" tone={data.summary.total ? "red" : "green"} />
            <StatCard value={data.summary.critical} label="CRITICAL" tone="red" />
            <StatCard value={data.summary.alarm} label="ALARM" tone="orange" />
            <StatCard value={data.summary.warn} label="WARN" tone="neutral" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="ios-section-title">机台分布 Top {data.by_eqp.length}</div>
              <Card className="space-y-2.5">
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
              </Card>
            </div>
            <div>
              <div className="ios-section-title">告警明细</div>
              <Card className="p-0 max-h-[420px] overflow-y-auto">
                {data.alarms.map((a, i) => (
                  <div key={i} className="flex items-center gap-3 px-4 py-2.5 border-b border-black/5 dark:border-white/5 last:border-0">
                    <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${LEVEL_TONE[a.level] || ""}`}>{a.level}</span>
                    <span className="font-medium text-[13px] w-[86px]">{a.eqp_id}</span>
                    <span className="flex-1 text-[13px] truncate" title={a.message}>{a.message}</span>
                    <span className="text-[11.5px] text-ios-label2">{a.dt}</span>
                  </div>
                ))}
                {!data.alarms.length && <div className="px-4 py-6 text-center text-ios-label2 text-[13px]">当前窗口内没有未处理告警</div>}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
