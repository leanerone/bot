"""B3: Microsoft Teams 通知渠道 (公司内网无外网企微, Teams 为默认群通知)。

双格式适配 (Microsoft 已宣布 O365 Connector 退役, 新装环境应使用 Power Automate):
- teams_format=connector  O365 Connector Incoming Webhook, MessageCard JSON (兼容存量)
- teams_format=flow       Power Automate "收到 webhook 时" 触发器, Adaptive Card JSON (推荐)

用法:
    from app.notify.teams import send_teams
    send_teams("ETCH-02 报 E0010 射频功率漂移 (ALARM)")

卡片分级配色: CRITICAL 红 / ALARM 橙 / WARN 黄 (teams_alarm_card)。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx

from app.api.audit import record as audit_record
from app.config import cfg

_TIMEOUT = 10.0

_LEVEL_COLOR = {"CRITICAL": "C00000", "ALARM": "ED6C02", "WARN": "E6B800"}


class TeamsError(RuntimeError):
    pass


def _parse_level(text: str) -> str:
    for lv in _LEVEL_COLOR:
        if lv in text.upper():
            return lv
    return "INFO"


def connector_card(text: str) -> Dict[str, Any]:
    """O365 Connector MessageCard 格式。"""
    level = _parse_level(text)
    return {
        "@type": "MessageCard",
        "@context": "http://schema.office.com/01/office/teams",
        "themeColor": _LEVEL_COLOR.get(level, "2F5AC6"),
        "summary": f"Fab Bot 通知 ({level})",
        "title": f"Fab Bot · {level}",
        "text": text,
    }


def flow_card(text: str) -> Dict[str, Any]:
    """Power Automate webhook 触发器: body 即 Adaptive Card (Post adaptive card 动作)。
    惯例包裹 {"adaptiveCard": {...}} 供 Flow 表达式取值。"""
    level = _parse_level(text)
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": f"Fab Bot · {level}", "weight": "Bolder",
             "color": "Attention" if level == "CRITICAL" else ("Warning" if level == "ALARM" else "Default")},
            {"type": "TextBlock", "text": text, "wrap": True},
        ],
    }
    return {"adaptiveCard": card, "level": level}


def _post(url: str, payload: Dict[str, Any], fmt: str, user: str) -> Dict[str, Any]:
    if not url:
        raise TeamsError("teams webhook 未配置 (config.yaml -> notify.teams_webhook)")
    try:
        resp = httpx.post(url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        audit_record(user, f"/notify/teams[{fmt}]", "notify",
                     json.dumps(payload, ensure_ascii=False)[:150], 0, status="fail")
        raise TeamsError(f"teams webhook 推送失败: {exc}") from exc
    audit_record(user, f"/notify/teams[{fmt}]", "notify",
                 json.dumps(payload, ensure_ascii=False)[:150], 0)
    return {"status": resp.status_code, "format": fmt}


def send_teams(text: str, user: str = "system",
               url: Optional[str] = None, fmt: Optional[str] = None) -> Dict[str, Any]:
    """统一入口: 按 config notify.teams_format 选择格式 (可显式覆盖)。"""
    url = url or cfg("notify.teams_webhook", "")
    fmt = (fmt or cfg("notify.teams_format", "connector")).lower()
    payload = connector_card(text) if fmt == "connector" else flow_card(text)
    return _post(url, payload, fmt, user)


def send_teams_alarm(text: str, alarms: list, user: str = "system") -> Dict[str, Any]:
    """告警卡片: 明细表 + 机台分布 (Teams 卡片用 Markdown 表格)。"""
    level = _parse_level(text)
    rows = "\n".join(
        f"| {a.get('dt','')} | {a.get('eqp_id','')} | {a.get('level','')} | {a.get('code','')} |"
        for a in alarms[:10]
    )
    by_eqp: Dict[str, int] = {}
    for a in alarms:
        by_eqp[a.get("eqp_id", "?")] = by_eqp.get(a.get("eqp_id", "?"), 0) + 1
    dist = " · ".join(f"{k}×{v}" for k, v in sorted(by_eqp.items(), key=lambda kv: -kv[1])[:8])
    rich = (
        f"{text}\n\n**未处理 {len(alarms)} 条** ({level})\n\n"
        f"机台分布: {dist}\n\n| 时间 | 机台 | 级别 | 告警码 |\n|---|---|---|---|\n{rows}"
    )
    url = cfg("notify.teams_webhook", "")
    fmt = (cfg("notify.teams_format", "connector") or "connector").lower()
    payload = connector_card(rich) if fmt == "connector" else flow_card(rich)
    return _post(url, payload, fmt, user)
