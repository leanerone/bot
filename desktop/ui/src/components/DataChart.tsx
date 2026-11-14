import React, { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

export interface ChartSeries { name: string; points: { x: string; y: number }[] }
export type ChartKind = "line" | "bar";

/* A5: 图表主题化 —— 色板固化为 token, 网格/文字/tooltip 跟随暗色主题 */
const COLORS = ["#0A84FF", "#FF9500", "#30D158", "#FF453A", "#BF5AF2", "#64D2FF"];

function useChartTheme() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const root = document.documentElement;
    const update = () => setDark(root.classList.contains("dark"));
    update();
    const mo = new MutationObserver(update);
    mo.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => mo.disconnect();
  }, []);
  return dark;
}

/** 折线/柱状图 (recharts 封装, iOS 色板, 主题感知) */
export default function DataChart({ series, kind = "line", height = 260 }: {
  series: ChartSeries[]; kind?: ChartKind; height?: number;
}) {
  const dark = useChartTheme();
  const grid = dark ? "rgba(120,120,128,.28)" : "rgba(120,120,128,.2)";
  const tick = { fontSize: 11, fill: dark ? "#98A2B3" : "#6E7681" };
  const tooltipStyle = {
    fontSize: 12, borderRadius: 10,
    background: dark ? "#1C1C1E" : "#FFFFFF",
    border: `1px solid ${dark ? "rgba(255,255,255,.12)" : "rgba(0,0,0,.08)"}`,
    color: dark ? "#F2F2F7" : "#1C1C1E",
  };

  // recharts 需要宽表: [{x: 值, [name]: 值}]
  const xKeys: string[] = [];
  for (const s of series) for (const p of s.points) if (!xKeys.includes(p.x)) xKeys.push(p.x);
  const data = xKeys.sort().map(x => {
    const row: Record<string, string | number> = { x };
    for (const s of series) {
      const hit = s.points.find(p => p.x === x);
      row[s.name] = hit ? hit.y : 0;
    }
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={height}>
      {kind === "line" ? (
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} />
          <XAxis dataKey="x" tick={tick} tickFormatter={(v: string) => v.slice(5)} />
          <YAxis tick={tick} domain={["auto", "auto"]} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12, color: tick.fill as string }} />
          {series.map((s, i) => (
            <Line key={s.name} type="monotone" dataKey={s.name} stroke={COLORS[i % COLORS.length]}
              strokeWidth={2} dot={false} />
          ))}
        </LineChart>
      ) : (
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} />
          <XAxis dataKey="x" tick={tick} tickFormatter={(v: string) => v.slice(5)} />
          <YAxis tick={tick} allowDecimals={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12, color: tick.fill as string }} />
          {series.map((s, i) => (
            <Bar key={s.name} dataKey={s.name} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      )}
    </ResponsiveContainer>
  );
}
