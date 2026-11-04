"""意图路由 v2: 加权信号评分, 替代 v3 的单正则粗分。

评分模型:
- 强业务信号 (机台/告警/良率/批次...) 权重高 —— 数据查询的可靠指示
- 动作词 (查/统计/多少/排名...) 权重中
- 知识问法 (怎么处理/为什么/是什么...) 为负分 —— 防"处理步骤"类问题误入 SQL
- 总分 >= 阈值判为数据查询, 否则知识问答

调参方式: 修改下方表 + 跑 python eval/run_eval.py 与 tests/test_intent.py 回归;
后续可平滑切换为模型意图分类 (本模块仅暴露 classify() 一个入口)。
"""
from __future__ import annotations

import re
from typing import List

# (模式, 权重) —— 顺序不影响结果, 便于审阅
STRONG_SIGNALS: List[tuple] = [
    (r"告警|报警|alarm", 3),
    (r"良率|合格率|die_yield|yield", 3),
    (r"wip|在制|批次|lot\b", 3),
    (r"spc|fdc", 3),
    (r"机台|设备|eqp|eqp_group", 2),
    (r"投片|片数|wafer", 2),
]
ACTION_SIGNALS: List[tuple] = [
    (r"多少|几个|几台|数量|统计|查询|查一下|查一下|排名|top|趋势|平均|最近|列表|count|list", 2),
    (r"怎么查|如何查|怎么看", 2),
]
NEGATIVE_SIGNALS: List[tuple] = [
    (r"怎么处理|如何处理|怎么办|怎么解决|处置步骤|处理步骤|处理方法", -3),
    (r"为什么|是什么|什么意思|原因|定义|注意什么|哪些信息", -2),
]

DEFAULT_THRESHOLD = 2


def classify(question: str, threshold: int = DEFAULT_THRESHOLD) -> dict:
    """返回 {"intent": "sql"|"kb", "score": int, "signals": [(信号, 权重)]}。"""
    q = question or ""
    score = 0
    signals: List[tuple] = []
    for group in (STRONG_SIGNALS, ACTION_SIGNALS, NEGATIVE_SIGNALS):
        for pattern, weight in group:
            if re.search(pattern, q, re.I):
                score += weight
                signals.append((pattern[:12], weight))
    intent = "sql" if score >= threshold else "kb"
    return {"intent": intent, "score": score, "signals": signals}
