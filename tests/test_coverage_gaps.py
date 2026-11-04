"""覆盖盲区补充测试: LLM 流式协议 / MES 适配器 / 知识库重建 / 守护开关 / Domino 客户端。"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi.testclient import TestClient

from app.adapters.mock_mes import MockMESAdapter, seed_demo_db
from app.store import db


# ── MES 适配器 (基于真实演示库) ──

def test_mock_mes_adapter_methods():
    dbp = Path(tempfile.mkdtemp()) / "fab.db"
    seed_demo_db(dbp, force=True)
    a = MockMESAdapter(dbp)
    lots = a.get_eqp_status()
    assert lots and {"eqp_id", "eqp_group", "vendor", "status"} <= set(lots[0])
    some = a.get_eqp_status(group="ETCH")
    assert all(e["eqp_group"] == "ETCH" for e in some) and some
    w = a.get_lot(lots[0]["eqp_id"])  # lot_id 与 eqp_id 不可能相同 -> None
    assert w is None or {"lot_id", "product"} <= set(w)
    assert a.get_alarms(hours=24 * 8, only_open=False)  # 有历史告警


# ── LLM 网关: 真实协议解析 (MockTransport 模拟 vLLM) ──

def _patch_httpx(handler):
    real_client = httpx.Client
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        kwargs.setdefault("transport", transport)
        return real_client(**kwargs)

    return factory


def test_openai_llm_chat_and_stream(monkeypatch=None):
    from app.llm.client import OpenAICompatLLM

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.read()))
        if b'"stream":true' in request.read().replace(b" ", b""):
            sse = (
                'data: {"choices":[{"delta":{"content":"第一段"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"第二段"}}]}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, text=sse)
        return httpx.Response(200, json={"choices": [{"message": {"content": "整段回答"}}]})

    orig_client, orig_post = httpx.Client, httpx.post
    httpx.Client = _patch_httpx(handler)

    def fake_post(url, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            return client.post(url, **kwargs)

    httpx.post = fake_post
    try:
        llm = OpenAICompatLLM("http://vllm.test/v1", "EMPTY", "test-model")
        assert llm.chat([{"role": "user", "content": "你好"}]) == "整段回答"
        assert calls[-1]["model"] == "test-model"
        chunks = list(llm.chat_stream([{"role": "user", "content": "你好"}]))
        assert chunks == ["第一段", "第二段"]
    finally:
        httpx.Client, httpx.post = orig_client, orig_post


def test_openai_llm_connection_error():
    from app.llm.client import LLMError, OpenAICompatLLM

    orig = httpx.Client
    httpx.Client = _patch_httpx(lambda request: httpx.Response(500, text="boom"))
    try:
        llm = OpenAICompatLLM("http://vllm.test/v1", "EMPTY", "m")
        try:
            llm.chat([{"role": "user", "content": "x"}])
            raise AssertionError("500 应抛 LLMError")
        except LLMError:
            pass
    finally:
        httpx.Client = orig


# ── 管理端: 知识库重建 + 推送测试端点 ──

def test_admin_kb_rebuild_end_to_end():
    _setup(Path(tempfile.mkdtemp()) / "rebuild.db")
    with TestClient(app) as c:
        _login(c)
        r = c.post("/api/admin/kb/rebuild")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] and body["kb_chunks"] > 0
        assert body["knowledge"]["chunks"] > 0
        # 重建后问答仍正常
        r2 = c.post("/api/chat", json={"question": "射频功率漂移怎么处理"})
        assert r2.status_code == 200 and r2.json()["type"] == "kb"


def test_admin_notify_test_unconfigured():
    _setup(Path(tempfile.mkdtemp()) / "notify.db")
    from app.config import CFG

    CFG.setdefault("notify", {})["wechat_webhook"] = ""
    with TestClient(app) as c:
        _login(c)
        r = c.post("/api/admin/notify/test", json={"platform": "wechat", "text": "x"})
        assert r.status_code == 400  # 未配置 webhook


# ── 守护线程开关 ──

def test_watcher_start_disabled_and_enabled():
    from app.config import CFG
    from app.watcher.alarm_watcher import start_if_enabled

    CFG.setdefault("watcher", {})["enabled"] = False
    assert start_if_enabled() is None

    CFG["watcher"]["enabled"] = True
    CFG["watcher"]["interval_minutes"] = 60
    CFG["watcher"]["platform"] = "none"  # 不发网络请求
    w = start_if_enabled()
    assert w is not None and w.is_alive()
    w.stop()
    CFG["watcher"]["enabled"] = False


# ── Domino 客户端协议解析 (MockTransport) ──

def test_domino_client_protocol():
    from app.adapters.hcl_notes import DominoNotesClient

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "ReadViewEntries" in url:
            return httpx.Response(200, json={
                "viewentry": [
                    {"@unid": "UNID1", "entrydata": [{"@columnnumber": "0", "text": {"0": "标题A"}}]},
                    {"@position": "2"},  # 无 unid, 应跳过
                    {"@unid": "UNID2"},
                ]})
        if "?OpenDocument" in url:
            unid = url.split("/")[-1].split("?")[0]
            return httpx.Response(200, text=f"<html><title>文档-{unid}</title><body>x</body></html>")
        return httpx.Response(404)

    orig = httpx.Client
    httpx.Client = _patch_httpx(handler)
    try:
        client = DominoNotesClient("https://domino.test", "kb/x.nsf", "u", "p")
        unids = client.list_unids()
        assert unids == ["UNID1", "UNID2"]
        html = client.fetch_doc_html("UNID1")
        assert "文档-UNID1" in html
        docs = list(client.iter_docs())
        assert docs[0].subject == "文档-UNID1" and docs[0].unid == "UNID1"
        assert docs[1].subject == "文档-UNID2"
    finally:
        httpx.Client = orig


# ── 直连入口的会话持久化 ──

def test_kb_ask_and_data_query_with_session():
    _setup(Path(tempfile.mkdtemp()) / "direct.db")
    with TestClient(app) as c:
        _login(c)
        sess = c.post("/api/sessions", json={"title": "直连"}).json()["session"]
        r = c.post("/api/kb/ask", json={"question": "射频功率漂移怎么处理", "session_id": sess["id"]})
        assert r.status_code == 200 and r.json()["session_id"] == sess["id"]
        r2 = c.post("/api/data/query", json={"question": "最近未处理的告警有哪些", "session_id": sess["id"]})
        assert r2.status_code == 200
        msgs = c.get(f"/api/sessions/{sess['id']}/messages").json()["messages"]
        assert len(msgs) == 4  # 2x(user+assistant)


# ── 公共辅助 ──

def _setup(path):
    db.use(path)


def _login(client, u="admin", p="admin123"):
    r = client.post("/api/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text


from app.main import app  # noqa: E402  (置于辅助函数后, 供上面的用例使用)
