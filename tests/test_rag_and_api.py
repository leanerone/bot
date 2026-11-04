"""RAG 分块/embedding 与 API 端到端测试 (mock 模式, 含登录)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.embedder import MockEmbedder
from app.rag.ingest import chunk_text


def test_chunk_text_sizes():
    text = "\n\n".join(f"段落{i} " + "字" * 60 for i in range(10))
    chunks = chunk_text(text, size=100, overlap=20)
    assert len(chunks) > 3
    assert all(len(c) <= 100 for c in chunks)


def test_chunk_text_long_para_overlap():
    text = "字" * 300
    chunks = chunk_text(text, size=100, overlap=20)
    assert chunks[1][:20] == chunks[0][-20:]  # 重叠保留


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_mock_embedder_similarity():
    e = MockEmbedder()
    v1 = e.embed_one("刻蚀机台射频功率漂移怎么处理")
    v2 = e.embed_one("刻蚀机台射频功率漂移的处置步骤")
    v3 = e.embed_one("今天天气很好适合外出跑步")
    assert _dot(v1, v2) > _dot(v1, v3)


def _login(client, username="admin", password="admin123"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["user"]


def test_api_end_to_end():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:  # 触发 bootstrap: 建库/账号/演示库 + 导入知识库
        _login(client)
        r = client.post("/api/chat", json={"question": "最近未处理的告警有哪些"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["type"] == "sql" and "sql" in data and data["row_count"] >= 0
        assert data["session_id"]  # 服务端会话已创建

        # 会话消息已持久化
        msgs = client.get(f"/api/sessions/{data['session_id']}/messages").json()["messages"]
        assert len(msgs) == 2 and msgs[0]["role"] == "user" and msgs[1]["role"] == "assistant"

        # 反馈
        fb = client.post("/api/feedback", json={"message_id": data["assistant_message_id"], "rating": "up"})
        assert fb.status_code == 200

        r2 = client.post("/api/chat", json={"question": "射频功率漂移的处置步骤是什么"})
        assert r2.status_code == 200, r2.text
        data2 = r2.json()
        assert data2["type"] == "kb" and data2["sources"], data2

        r3 = client.get("/api/health")
        assert r3.status_code == 200 and r3.json()["kb_chunks"] > 0


def test_api_chat_stream_sql():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        _login(client)
        with client.stream("POST", "/api/chat/stream",
                           json={"question": "最近未处理的告警有哪些"}) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())
        assert "event: meta" in body and "event: result" in body and '"sql"' in body
        assert "session_id" in body  # meta 事件携带会话


def test_api_chat_stream_kb():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        _login(client)
        with client.stream("POST", "/api/chat/stream",
                           json={"question": "射频功率漂移的处置步骤",
                                 "history": [{"role": "user", "content": "机台异常怎么办"}]}) as resp:
            assert resp.status_code == 200
            body = "".join(resp.iter_text())
        assert "event: delta" in body and "event: done" in body and "sources" in body


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
