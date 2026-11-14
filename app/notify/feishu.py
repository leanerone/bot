"""飞书群机器人 webhook (可选渠道, 供混合部署环境使用)。"""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.api.audit import record as audit_record
from app.config import cfg

_TIMEOUT = 10.0


class FeishuError(RuntimeError):
    pass


def _payload(text: str) -> Dict[str, Any]:
    return {"msg_type": "text", "content": {"text": f"[Fab Bot] {text}"}}


def send_feishu(text: str, user: str = "system", url: Optional[str] = None) -> Dict[str, Any]:
    url = url or cfg("notify.feishu_webhook", "")
    if not url:
        raise FeishuError("feishu webhook 未配置 (config.yaml -> notify.feishu_webhook)")
    try:
        resp = httpx.post(url, json=_payload(text), timeout=_TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        audit_record(user, "/notify/feishu", "notify", text[:150], 0, status="fail")
        raise FeishuError(f"feishu webhook 推送失败: {exc}") from exc
    audit_record(user, "/notify/feishu", "notify", text[:150], 0)
    return {"status": resp.status_code}
