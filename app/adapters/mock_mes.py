"""演示数据生成 + Mock 适配器实现。

生成一张"缩小版 Fab"演示库: 机台/在制/良率/告警四张表, 让 Text2SQL
在没有真实 MES 的环境下也能端到端演示。
"""
from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.adapters.base import MESAdapter
from app.config import abs_path
from app.sqlbot.schema import DEMO_DDL

DEMO_DB = abs_path("data/demo/fab_demo.db")


def seed_demo_db(db_path: Optional[Path] = None, force: bool = False) -> Path:
    db_path = Path(db_path) if db_path else DEMO_DB
    if force and db_path.exists():
        db_path.unlink()  # 强制重种: 直接删除旧库文件, 避免表冲突
    if db_path.exists():
        return db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    for ddl in DEMO_DDL:
        conn.execute(ddl)

    random.seed(42)
    today = date.today()

    # 机台: 6 个群组共 13 台
    eqps: List[tuple] = []
    for group, vendor, n in [
        ("LITHO", "ASML", 3), ("ETCH", "LAM", 3), ("CMP", "AMAT", 2),
        ("DEP", "AMAT", 2), ("DIFF", "TEL", 1), ("METRO", "KLA", 2),
    ]:
        for i in range(1, n + 1):
            status = random.choices(["RUN", "IDLE", "DOWN", "PM"], weights=[0.6, 0.15, 0.15, 0.1])[0]
            eqps.append((f"{group}-{i:02d}", group, vendor, status))
    conn.executemany("INSERT INTO eqp VALUES (?,?,?,?)", eqps)

    # 在制品 40 批
    products = ["P1234", "P2233", "P3121", "P4122"]
    layers = ["AA", "CONTACT", "VIA1", "M1", "M2"]
    lots = []
    for i in range(1, 41):
        lots.append((
            f"A24{i:05d}", random.choice(products), random.choice(layers),
            random.randint(100, 800), random.choice([24, 25]),
            random.choice([e[0] for e in eqps] + ["", ""]),  # 部分批次未上机台
        ))
    conn.executemany("INSERT INTO wip VALUES (?,?,?,?,?,?)", lots)

    # 每日良率: 30 天 x 4 产品
    yrows = []
    for d in range(30, 0, -1):
        dt = (today - timedelta(days=d)).isoformat()
        for p in products:
            yrows.append((dt, p, random.randint(18, 25), round(random.uniform(0.90, 0.975), 4)))
    conn.executemany("INSERT INTO yield_daily VALUES (?,?,?,?)", yrows)

    # 告警 50 条 (近 7 天)
    codes = [
        ("E0010", "RF_PWR_DRIFT 射频功率漂移"),
        ("C2201", "CHAMBER_PRESS 腔压越限"),
        ("T0305", "TEMP_DEV 温度漂移"),
        ("V0102", "VACUUM_ABNORMAL 真空异常"),
    ]
    arows = []
    for i in range(1, 51):
        code, msg = random.choice(codes)
        arows.append((
            i,
            (today - timedelta(hours=random.randint(1, 24 * 7))).strftime("%Y-%m-%d %H:%M"),
            random.choice(eqps)[0],
            random.choices(["WARN", "ALARM", "CRITICAL"], weights=[0.5, 0.35, 0.15])[0],
            code, msg, random.choice([0, 0, 1]),
        ))
    conn.executemany("INSERT INTO alarms VALUES (?,?,?,?,?,?,?)", arows)

    conn.commit()
    conn.close()
    return db_path


class MockMESAdapter(MESAdapter):
    """演示实现: 直接读演示库。真实工厂按同样方法签名对接中间库/API。"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEMO_DB

    def get_lot(self, lot_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM wip WHERE lot_id = ?", (lot_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_eqp_status(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        if group:
            rows = conn.execute("SELECT * FROM eqp WHERE eqp_group = ?", (group,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM eqp").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_alarms(self, hours: int = 24, only_open: bool = True) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM alarms WHERE dt >= datetime('now', 'localtime', ?)"
        if only_open:
            sql += " AND handled = 0"
        rows = conn.execute(sql, (f"-{hours} hours",)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_wip_count(self) -> int:
        conn = sqlite3.connect(str(self.db_path))
        n = conn.execute("SELECT COUNT(*) FROM wip").fetchone()[0]
        conn.close()
        return n

    def get_alarms_since(self, after_id: int = 0, levels: Optional[List[str]] = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """按 id 游标取新增告警 (通知轮询用), id 升序。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        levels = levels or ["CRITICAL", "ALARM"]
        placeholders = ",".join("?" for _ in levels)
        rows = conn.execute(
            f"SELECT * FROM alarms WHERE id > ? AND handled = 0 "
            f"AND level IN ({placeholders}) ORDER BY id ASC LIMIT ?",
            (after_id, *levels, min(limit, 200)),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
