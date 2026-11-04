"""通知模块测试 (httpx MockTransport 模拟 webhook)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.notify import webhook


def test_wechat_payload_format():
    p = webhook._wechat_payload("ETCH-02 告警")
    assert p["msgtype"] == "text" and p["text"]["content"].startswith("[Fab Bot]")
    assert webhook.text_summary(p) == "[Fab Bot] ETCH-02 告警"


def test_send_via_mock_transport(monkeypatch=None):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read()
        return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

    real_post = httpx.post

    def fake_post(url, **kwargs):
        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            return client.post(url, **kwargs)

    httpx.post = fake_post
    try:
        # 临时配置 webhook 地址
        from app.config import CFG
        CFG.setdefault("notify", {})["wechat_webhook"] = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=TEST"
        result = webhook.send_wechat("测试告警推送", user="admin")
        assert result["errcode"] == 0
        assert b"[Fab Bot]" in captured["body"]
        assert "key=TEST" in captured["url"]
    finally:
        httpx.post = real_post


def test_unconfigured_raises():
    from app.config import CFG
    CFG.setdefault("notify", {})["dingtalk_webhook"] = ""
    try:
        webhook.send_dingtalk("x")
        raise AssertionError("未配置 webhook 应报错")
    except webhook.NotifyError:
        pass


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
