"""演示库表结构 + 语义层描述 (Text2SQL 的核心: 表结构 + 业务黑话说明 + few-shot)。

真实工厂接入时, 用同样的格式补充 MES/FDC 只读中间库的表说明即可 ——
schema 描述写得越"像工程师说的话", Text2SQL 准确率越高。
"""

TABLES = {
    "eqp": """
CREATE TABLE eqp (             -- 机台主数据
  eqp_id     TEXT PRIMARY KEY, -- 机台编号, 如 ETCH-01
  eqp_group  TEXT,             -- 机台群组: LITHO/ETCH/CMP/DEP/DIFF/METRO
  vendor     TEXT,             -- 设备厂商
  status     TEXT              -- 当前状态: RUN/IDLE/DOWN/PM
);""",
    "wip": """
CREATE TABLE wip (             -- 在制品 (当前批次)
  lot_id     TEXT PRIMARY KEY, -- 批次号, 如 A240001
  product    TEXT,             -- 产品型号, 如 P1234
  layer      TEXT,             -- 当前工艺层: AA/CONTACT/VIA1/M1/M2
  route_step INTEGER,          -- 当前站序
  qty        INTEGER,          -- 批量(片)
  eqp_id     TEXT              -- 当前所在机台 (可空)
);""",
    "yield_daily": """
CREATE TABLE yield_daily (     -- 每日良率
  dt        TEXT,              -- 日期 (YYYY-MM-DD)
  product   TEXT,              -- 产品型号
  wafer_qty INTEGER,            -- 投片数
  die_yield REAL,               -- 裸片良率 (0~1)
  PRIMARY KEY (dt, product)
);""",
    "alarms": """
CREATE TABLE alarms (          -- 设备告警记录
  id      INTEGER PRIMARY KEY,
  dt      TEXT,                -- 告警时间 (YYYY-MM-DD HH:MM)
  eqp_id  TEXT,                -- 机台编号
  level   TEXT,                -- 级别: WARN/ALARM/CRITICAL
  code    TEXT,                -- 告警码
  message TEXT,                -- 告警描述
  handled INTEGER              -- 是否已处理: 0 未处理 / 1 已处理
);""",
}

# 演示库建表语句 (mock_mes 生成数据时使用, 单一来源)
DEMO_DDL = list(TABLES.values())

# 给 LLM 看的 schema 文本
SCHEMA_TEXT = "\n".join(TABLES.values())

FEWSHOT = """问: ETCH 区现在有几台机台是 DOWN 的?
SELECT COUNT(*) AS cnt FROM eqp WHERE eqp_group = 'ETCH' AND status = 'DOWN';

问: 最近一周 P1234 的平均良率是多少?
SELECT AVG(die_yield) AS avg_yield FROM yield_daily WHERE product = 'P1234'
  AND dt >= DATE('now', 'localtime', '-7 day');

问: 最近 10 条未处理的告警?
SELECT dt, eqp_id, level, code, message FROM alarms WHERE handled = 0 ORDER BY dt DESC LIMIT 10;"""
