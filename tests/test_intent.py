"""意图路由 v2 测试: 覆盖典型问法与易混淆问法。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.intent import classify

SQL_CASES = [
    "最近未处理的告警有哪些",
    "ETCH 区现在有几台机台是 DOWN 的？",
    "最近一周 P1234 的平均良率是多少？",
    "机台状态怎么查",
    "良率数据最近的情况",
    "查一下在制 wip 数量",
    "最近 10 条告警",
    "机台告警排名 top5",
]
KB_CASES = [
    "射频功率漂移怎么处理？",
    "腔压越限的处置步骤是什么？",
    "机台做完 PM 后恢复生产要注意什么？",
    "良率波动排查的顺序是什么？",
    "什么叫 Q-time？超时了怎么办？",
    "为什么良率会突然下降？",
    "光刻胶异常是什么原因？",
    "怎么处理 E0010 告警？",
]


def test_sql_intents():
    for q in SQL_CASES:
        r = classify(q)
        assert r["intent"] == "sql", f"{q!r} -> {r}"


def test_kb_intents():
    for q in KB_CASES:
        r = classify(q)
        assert r["intent"] == "kb", f"{r['score']} {q!r} -> {r}"


def test_result_shape():
    r = classify("最近未处理的告警有哪些")
    assert r["intent"] in ("sql", "kb")
    assert isinstance(r["score"], int)
    assert all(isinstance(s, tuple) and len(s) == 2 for s in r["signals"])


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
