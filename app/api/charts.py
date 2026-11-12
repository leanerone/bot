"""数据台预置图表端点: 直连演示库聚合 (免 LLM, 稳定可测)。"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Request

from app.adapters.mock_mes import DEMO_DB
from app.api.deps import require_user

router = APIRouter(prefix="/api/data/charts")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DEMO_DB))
    conn.row_factory = sqlite3.Row
    return conn


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


@router.get("/yield-trend")
def yield_trend(request: Request, days: int = 30):
    """各产品每日平均良率 (折线, 按产品分系列)。"""
    require_user(request)
    days = min(max(days, 3), 90)
    since = _days_ago(days)
    conn = _conn()
    rows = conn.execute(
        """SELECT dt, product, AVG(die_yield) AS avg_yield FROM yield_daily
           WHERE dt >= ? GROUP BY dt, product ORDER BY dt""",
        (since,),
    ).fetchall()
    conn.close()

    by_product: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_product.setdefault(r["product"], []).append({"x": r["dt"], "y": round(r["avg_yield"], 4)})
    series = [{"name": k, "points": v} for k, v in sorted(by_product.items())]
    return {"days": days, "metric": "die_yield", "series": series}


@router.get("/alarm-by-day")
def alarm_by_day(request: Request, days: int = 14):
    """未处理告警按日按级别计数 (堆叠柱状)。"""
    require_user(request)
    days = min(max(days, 3), 60)
    since = _days_ago(days)
    conn = _conn()
    rows = conn.execute(
        """SELECT substr(dt, 1, 10) AS day, level, COUNT(*) AS cnt FROM alarms
           WHERE dt >= ? AND handled = 0 GROUP BY day, level ORDER BY day""",
        (since,),
    ).fetchall()
    conn.close()

    by_level: Dict[str, Dict[str, int]] = {}
    for r in rows:
        day = r["day"]
        by_level.setdefault(day, {"x": day, "CRITICAL": 0, "ALARM": 0, "WARN": 0})
        if r["level"] in by_level[day]:
            by_level[day][r["level"]] += r["cnt"]
    series_map: Dict[str, List[Dict[str, Any]]] = {}
    for day_counts in sorted(by_level.values(), key=lambda d: d["x"]):
        for lvl in ("CRITICAL", "ALARM", "WARN"):
            series_map.setdefault(lvl, []).append({"x": day_counts["x"], "y": day_counts[lvl]})
    series = [{"name": lvl, "points": pts} for lvl, pts in sorted(series_map.items())]
    return {"days": days, "metric": "open_alarms", "series": series}
