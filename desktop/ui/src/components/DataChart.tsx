import React from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

export interface ChartSeries { name: string; points: { x: string; y: number }[] }
export type ChartKind = "line" | "bar";

const COLORS = ["#0A84FF", "#FF9500", "#30D158", "#FF453A", "#BF5AF2", "#64D2FF"];

/** 折线/柱状图 (recharts 封装, iOS 色板) */
export default function DataChart({ series, kind = "line", height = 260 }: {
  series: ChartSeries[]; kind?: ChartKind; height?: number;
}) {
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
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(120,120,128,.2)" />
          <XAxis dataKey="x" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
          <YAxis tick={{ fontSize: 11 }} domain={["auto", "auto"]} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s, i) => (
            <Line key={s.name} type="monotone" dataKey={s.name} stroke={COLORS[i % COLORS.length]}
              strokeWidth={2} dot={false} />
          ))}
        </LineChart>
      ) : (
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(120,120,128,.2)" />
          <XAxis dataKey="x" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 10 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s, i) => (
            <Bar key={s.name} dataKey={s.name} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      )}
    </ResponsiveContainer>
  );
}
