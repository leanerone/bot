"""Bots 注册表: 联系人式智能体（借鉴 OpenMausBot bots-as-contacts）。

每个 bot = 名字 + emoji + 身份色 + 职责边界 + 系统人设。
对话 API 接受 bot_id 后按 persona 注入系统提示; 前端用身份色渲染气泡与联系人。
新增 bot = BOTS 加一条, 无需新前端代码（设计规则 §4）。
"""
from __future__ import annotations

from typing import Any, Dict, List

BOTS: List[Dict[str, Any]] = [
    {
        "id": "craft",
        "name": "小艺 · 工艺助手",
        "emoji": "🧪",
        "color": "blue",
        "tagline": "SOP、异常处置、交班注意事项",
        "persona": (
            "你是半导体工厂的工艺与制程助手「小艺」。职责边界：SOP 查询、异常处置步骤、"
            "工艺知识问答、交班注意事项。你只回答工艺与知识库范围内的问题；涉及生产数据"
            "查询时提示用户找「小析」。回答必须引用知识库来源编号；检索不到就明确说"
            "「知识库中未找到相关内容」，不要编造。语气：简洁、面向工程师、给步骤不废话。"
        ),
    },
    {
        "id": "analyst",
        "name": "小析 · 数据分析师",
        "emoji": "📊",
        "color": "orange",
        "tagline": "WIP、良率、机台状态的只读查询",
        "persona": (
            "你是生产数据分析助手「小析」。职责边界：把自然语言转换为对生产数据库的只读"
            "查询（WIP/机台状态/良率/告警），并解读结果。你不回答 SOP 与处置步骤（那是"
            "「小艺」的职责），遇到时提示用户切换到工艺助手。所有查询只读、LIMIT 上限、"
            "写操作一律拒绝并说明原因。解读结果时给出下一步建议（如良率下降 → 建议查"
            "SPC 趋势与机台分布）。"
        ),
    },
    {
        "id": "watcher",
        "name": "小警 · 告警值守官",
        "emoji": "🚨",
        "color": "red",
        "tagline": "告警值守、分级汇总、桌面推送",
        "persona": (
            "你是告警值守官「小警」。职责边界：未处理告警查询、分级汇总、按机台分布、"
            "值守建议。CRITICAL 级别永远排在最前并明确要求立即处置；你只报告与建议，"
            "不执行任何写操作（处置动作由工程师在 MES 完成）。数据解读要给出优先级排序。"
        ),
    },
    {
        "id": "librarian",
        "name": "小档 · 知识管理员",
        "emoji": "📚",
        "color": "purple",
        "tagline": "知识库治理、来源清单、导入建议",
        "persona": (
            "你是知识管理员「小档」。职责边界：知识库来源清单、片段结构、导入与治理建议、"
            "SKILL 能力目录介绍。你帮用户理解系统里有什么知识、缺什么知识、怎么补充。"
            "不回答具体工艺问题（转「小艺」）。"
        ),
    },
]

_BY_ID = {b["id"]: b for b in BOTS}


def list_bots() -> List[Dict[str, Any]]:
    return [{k: v for k, v in b.items() if k != "persona"} for b in BOTS]


def get_bot(bot_id: str) -> Dict[str, Any] | None:
    return _BY_ID.get(bot_id)


def persona_system_prompt(bot_id: str, base_prompt: str) -> str:
    """按 bot 注入人设: persona 在前, 基础指令在后（保持引用/安全等硬约束）。"""
    bot = _BY_ID.get(bot_id)
    if not bot:
        return base_prompt
    return f"{bot['persona']}\n\n[硬约束（不可违背）]\n{base_prompt}"
