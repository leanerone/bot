import React, { useState } from "react";
import { Me, postJSON } from "../api";
import { BigTitle, Card } from "../components/ui";

const SAMPLES = ["最近未处理的告警有哪些", "ETCH 区几台机台是 DOWN 的", "最近一周 P1234 的平均良率", "机台状态怎么查"];

export default function Data({ me }: { me: Me }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState("");

  const run = async (question?: string) => {
    const query = (question ?? q).trim();
    if (!query || busy) return;
    setBusy(true); setErr(""); setResult(null);
    try { setResult(await postJSON("/api/data/query", { question: query })); }
    catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="h-full overflow-y-auto px-6 pt-[46px] pb-6">
      <BigTitle sub="自然语言查生产数据 —— 只读安全，返回 SQL 与结果">数据台</BigTitle>
      <Card className="mb-4">
        <div className="flex gap-2">
          <input className="ios-input flex-1" placeholder="例：最近未处理的告警有哪些？"
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

      {err && <Card className="border-[#FF453A]/40 bg-[#FF453A]/5 !text-[#FF453A] text-[13.5px]">⚠️ {err}</Card>}
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
            <div className="px-4 py-2.5 border-b border-black/5 dark:border-white/5 text-[13px] font-semibold">
              查询结果 · {result.row_count} 行
            </div>
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
            {result.row_count > 200 && <div className="px-4 py-2 text-[11.5px] text-ios-label2">仅显示前 200 行</div>}
          </Card>
        </>
      )}

      {!result && !busy && !err && (
        <Card className="text-[13px] text-ios-label2 leading-6">
          数据来自只读中间库（演示库），支持自然语言查询 WIP / 机台状态 / 良率 / 告警。<br>
          </br>所有查询强制只读 SELECT 并限制返回行数，写操作一律拒绝。
        </Card>
      )}
    </div>
  );
}
