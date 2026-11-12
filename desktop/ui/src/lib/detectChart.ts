/** 查询结果智能切图: 判断表格数据适合折线/柱状/不可图表化 (纯函数, 可单测) */

const DATE_HINT = /(dt|date|时间|日期|day)/i;

function looksLikeDate(v: unknown): boolean {
  return typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v);
}

/** 返回 {kind, xKey, yKeys} —— kind=null 表示不可图表化 */
export function detectChart(columns: string[], rows: unknown[][]): {
  kind: "line" | "bar" | null; xKey: string; yKeys: string[];
} {
  if (!columns.length || rows.length < 2) return { kind: null, xKey: "", yKeys: [] };

  const numCol = (ci: number) => rows.slice(0, 8).every(r => typeof r[ci] === "number");
  const dateCol = (ci: number) =>
    DATE_HINT.test(columns[ci]) || rows.slice(0, 5).every(r => looksLikeDate(r[ci]));

  const dateIdx = columns.findIndex((_, ci) => dateCol(ci));
  const numeric = columns.map((_, ci) => ci).filter(ci => numCol(ci));
  const nonNum = columns.map((_, ci) => ci).filter(ci => !numCol(ci));

  // 日期/时间列做 X 轴 + 数值列做系列 → 折线
  if (dateIdx >= 0) {
    const yKeys = numeric.filter(ci => ci !== dateIdx).map(ci => columns[ci]);
    if (yKeys.length) return { kind: "line", xKey: columns[dateIdx], yKeys };
  }
  // 恰一个数值列 + 一个分类列 → 柱状
  if (numeric.length === 1 && nonNum.length >= 1) {
    return { kind: "bar", xKey: columns[nonNum[0]], yKeys: [columns[numeric[0]]] };
  }
  return { kind: null, xKey: "", yKeys: [] };
}
