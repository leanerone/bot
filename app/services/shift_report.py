"""交班报告聚合 (纯函数, 单测友好): 告警分级统计 + 良率均值 + WIP 分布 → Markdown。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from app.adapters.mock_mes import MockMESAdapter


def build_shift_report(hours: int = 12,
                       adapter: MockMESAdapter | None = None) -> Dict[str, Any]:
    adapter = adapter or MockMESAdapter()
    alarms = adapter.get_alarms(hours=hours, only_open=False)
    import sqlite3

    conn = sqlite3.connect(str(adapter.db_path))
    conn.row_factory = sqlite3.Row
    yrows = conn.execute(
        """SELECT product, AVG(die_yield) AS avg_yield FROM yield_daily
           WHERE dt >= DATE('now', 'localtime', '-7 day') GROUP BY product ORDER BY avg_yield"""
    ).fetchall()
    wrows = conn.execute(
        "SELECT product, COUNT(*) AS lots FROM wip GROUP BY product ORDER BY lots DESC"
    ).fetchall()
    conn.close()

    yield_series = [{"name": r["product"], "avg": round(r["avg_yield"], 4)} for r in yrows]
    wip = [{"product": r["product"], "lots": r["lots"]} for r in wrows]

    open_alarms = [a for a in alarms if a["handled"] == 0]
    critical = [a for a in open_alarms if a["level"] == "CRITICAL"]

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    md_lines = [
        f"# 交班报告（近 {hours} 小时）",
        f"",
        f"生成时间：{generated}",
        "",
        "## 一、未处理告警",
        f"- 未处理告警 **{len(open_alarms)}** 条（CRITICAL {len(critical)} 条）",
    ]
    for a in critical[:8]:
        md_lines.append(f"  - [{a['level']}] {a['eqp_id']} {a['code']} {a['message']} @ {a['dt']}")
    md_lines += ["", "## 二、近 7 天良率（按产品，升序=需关注）"]
    for y in yield_series:
        md_lines.append(f"- {y['name']}: 平均良率 **{y['avg']:.2%}**")
    md_lines += ["", "## 三、在制品分布"]
    for w in wip:
        md_lines.append(f"- {w['product']}: {w['lots']} 批")
    md_lines += ["", "## 四、交班注意事项（摘自知识库 FAQ）",
                 "- 未处理完的 CRITICAL 告警及其临时对策",
                 "- Hold 中的 lot 及 Hold 原因",
                 "- 当天计划 PM 与预计恢复时间"]

    return {
        "generated_at": generated,
        "hours": hours,
        "alarms": {"total_open": len(open_alarms), "critical": len(critical), "items": open_alarms[:20]},
        "yield": yield_series,
        "wip": wip,
        "markdown": "\n".join(md_lines),
    }
