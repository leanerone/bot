"""告警/通知推送: 企业微信 & 钉钉群机器人 webhook。

用法 (代码):
    from app.notify.webhook import send_wechat, send_dingtalk
    send_wechat("ETCH-02 报 C2201 腔压越限 (CRITICAL), 已持续 10 分钟")

用法 (接口, admin): POST /api/admin/notify/test {"platform": "wechat", "text": "..."}

安全说明: webhook 地址含密钥, 只写在服务端 config, 不要提交到公开仓库;
推送内容经过审计 (audit 表)。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.api.audit import record as audit_record
from app.config import cfg

_TIMEOUT = 10.0


class NotifyError(RuntimeError):
    pass


def _wechat_payload(text: str) -> Dict[str, Any]:
    return {"msgtype": "text", "text": {"content": f"[Fab Bot] {text}"}}


def _dingtalk_payload(text: str) -> Dict[str, Any]:
    return {"msgtype": "text", "text": {"content": f"[Fab Bot] {text}"}}


def _post(url: str, payload: Dict[str, Any], platform: str, user: str = "system") -> Dict[str, Any]:
    if not url or "HOOK" in url:
        raise NotifyError(f"{platform} webhook 未配置 (config.yaml -> notify)")
    try:
        resp = httpx.post(url, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        audit_record(user, f"/notify/{platform}", "", text_summary(payload), 0, status="fail")
        raise NotifyError(f"{platform} 推送失败: {exc}") from exc
    audit_record(user, f"/notify/{platform}", "", text_summary(payload), 0)
    return resp.json()


def text_summary(payload: Dict[str, Any]) -> str:
    try:
        return payload["text"]["content"][:120]
    except (KeyError, TypeError):
        return ""


def send_wechat(text: str, user: str = "system") -> Dict[str, Any]:
    url = cfg("notify.wechat_webhook", "")
    return _post(url, _wechat_payload(text), "wechat", user)


def send_dingtalk(text: str, user: str = "system") -> Dict[str, Any]:
    url = cfg("notify.dingtalk_webhook", "")
    return _post(url, _dingtalk_payload(text), "dingtalk", user)


def send(platform: str, text: str, user: str = "system") -> Optional[Dict[str, Any]]:
    """统一入口: platform in {wechat, dingtalk, both}。"""
    if platform == "wechat":
        return send_wechat(text, user)
    if platform == "dingtalk":
        return send_dingtalk(text, user)
    if platform == "both":
        return {"wechat": send_wechat(text, user), "dingtalk": send_dingtalk(text, user)}
    raise NotifyError(f"未知推送平台: {platform}")
