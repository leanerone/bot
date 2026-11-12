import React, { useEffect, useState } from "react";
import { Me, getJSON, postJSON } from "../api";
import { BigTitle, Card, Segmented } from "../components/ui";
import DataChart, { ChartSeries } from "../components/DataChart";
import { detectChart } from "../lib/detectChart";

const SAMPLES = ["最近未处理的告警有哪些", "ETCH 区几台机台是 DOWN 的", "最近一周 P1234 的平均良率", "机台状态怎么查"];

type QueryResult = { sql: string; columns: string[]; rows: any[][]; row_count: number };
type ChartResp = { days: number; metric: string; series: { name: string; points: { x: string; y: number }[] }[] };

export default function Data({ me }: { me: Me }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [err, setErr] = useState("");
  const [kind, setKind] = useState<"table" | "line" | "bar">("table");

  const [trend, setTrend] = useState<ChartResp | null>(null);
  const [alarmChart, setAlarmChart] = useState<ChartResp | null>(null);

  const run = async (question?: string) => {
    const query = (question ?? q).trim();
    if (!query || busy) return;
    setBusy(true); setErr(""); setResult(null); setKind("table");
    try { setResult(await postJSON("/api/data/query", { question: query })); }
    catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    getJSON<ChartResp>("/api/data/charts/yield-trend?days=30").then(setTrend).catch(() => {});
    getJSON<ChartResp>("/api/data/charts/alarm-by-day?days=14").then(setAlarmChart).catch(() => {});
  }, []);

  const detection = result ? detectChart(result.columns, result.rows) : { kind: null as null, xKey: "", yKeys: [] };
  const chartable = detection.kind !== null;
  const resultSeries: ChartSeries[] = detection.kind
    ? [{ name: detection.yKeys[0] || "值",
        points: result!.rows.map(r => ({
          x: String(r[result!.columns.indexOf(detection.xKey)]),
          y: Number(r[result!.columns.indexOf(detection.yKeys[0])]),
        })) }]
    : [];

  return (
    <div className="h-full overflow-y-auto px-6 pt-[46px] pb-6">
      <BigTitle sub="自然语言查生产数据 —— 只读安全，SQL + 表格 + 图表">数据台</BigTitle>
      <Card className="mb-4">
        <div className="flex gap-2">
          <input className="ios-input flex-1" placeholder="例：最近一周 P1234 的平均良率"
            value={q} onChange={e => setQ(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") run(); }} />
          <button className="ios-btn-primary px-5" disabled={busy || !q.trim()} onClick={() => run()}>
            {busy ? "查询中…" : "查询"}
          </button>
        </div>
        <div className="flex gap-1.5 mt-2.5 flex-wrap">
          {SAMPLES.map(s => (
            <button key={s} onClick={() => { setQ(s); run(s); }}
              className="text-[12px] px-2.5 py-1 rounded-full bg-black/[.04] dark:bg-white/[.06] hover:bg-black/10 transition-colors">{s}</button>
          ))}
        </div>
      </Card>

      {err && <Card className="mb-4 !border-[#FF453A]/40 !bg-[#FF453A]/5 text-[#FF453A] text-[13.5px]">⚠️ {err}</Card>}

      {/* 预置图表 */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {trend && trend.series.length > 0 && (
          <Card>
            <div className="text-[13px] font-semibold mb-2">📈 良率趋势（近 {trend.days} 天，按产品）</div>
            <DataChart series={trend.series} kind="line" />
          </Card>
        )}
        {alarmChart && alarmChart.series.some(s => s.points.some(p => p.y > 0)) && (
          <Card>
            <div className="text-[13px] font-semibold mb-2">📊 未处理告警分布（近 {alarmChart.days} 天，按级别）</div>
            <DataChart series={alarmChart.series} kind="bar" />
          </Card>
        )}
      </div>

      {busy && <Card><span className="text-[13px] text-ios-label2">查询中…（生成 SQL → 安全校验 → 只读执行）</span></Card>}

      {result && (
        <>
          <Card className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[13px] font-semibold">生成 SQL</span>
              <button className="text-[12px] text-ios-label2 hover:text-current"
                onClick={() => navigator.clipboard.writeText(result.sql)}>复制</button>
            </div>
            <pre className="bg-[#10161F] text-[#D8E2EF] rounded-[10px] p-3.5 text-[12.5px] overflow-x-auto">{result.sql}</pre>
          </Card>
          <Card className="p-0 overflow-hidden mb-4">
            <div className="px-4 py-2.5 border-b border-black/5 dark:border-white/5 flex items-center">
              <span className="text-[13px] font-semibold flex-1">查询结果 · {result.row_count} 行</span>
              {chartable && (
                <Segmented value={kind} onChange={setKind}
                  options={[{ value: "table", label: "表格" }, { value: "line", label: "折线" }, { value: "bar", label: "柱状" }]} />
              )}
            </div>
            {kind === "table" ? (
              <div className="overflow-x-auto max-h-[420px]">
                <table className="w-full text-[13px] border-collapse">
                  <thead><tr>{result.columns.map((c: string) =>
                    <th key={c} className="bg-black/[.03] dark:bg-white/[.05] text-left px-3 py-2 font-semibold sticky top-0">{c}</th>)}</tr></thead>
                  <tbody>
                    {result.rows.slice(0, 200).map((row: any[], i: number) => (
                      <tr key={i} className="border-t border-black/5 dark:border-white/5">
                        {row.map((v, j) => <td key={j} className="px-3 py-1.5">{String(v ?? "")}</td>)}
                      </tr>))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-4">
                <DataChart kind={kind === "line" ? "line" : "bar"} series={resultSeries} height={320} />
              </div>
            )}
            {result.row_count > 200 && <div className="px-4 py-2 text-[11.5px] text-ios-label2">仅显示前 200 行</div>}
          </Card>
        </>
      )}

      {!result && !busy && !err && (
        <Card className="text-[13px] text-ios-label2 leading-6">
          数据来自只读中间库（演示库），支持自然语言查询 WIP / 机台状态 / 良率 / 告警。<br />
          所有查询强制只读 SELECT 并限制返回行数，写操作一律拒绝。
        </Card>
      )}
    </div>
  );
}
