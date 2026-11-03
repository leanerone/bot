"""RAG 分块/embedding 与 API 端到端测试 (mock 模式)。"""
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


def test_api_end_to_end():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:  # 触发 bootstrap: 建演示库 + 导入知识库
        r = client.post("/api/chat", json={"question": "最近未处理的告警有哪些"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["type"] == "sql" and "sql" in data and data["row_count"] >= 0

        r2 = client.post("/api/chat", json={"question": "射频功率漂移的处置步骤是什么"})
        assert r2.status_code == 200, r2.text
        data2 = r2.json()
        assert data2["type"] == "kb" and data2["sources"], data2

        r3 = client.get("/api/health")
        assert r3.status_code == 200 and r3.json()["kb_chunks"] > 0


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
