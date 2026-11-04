"""混合检索测试: BM25 索引 + RRF 融合。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag import pipeline
from app.rag.bm25 import BM25Index, tokenize
from app.rag.embedder import MockEmbedder
from app.rag.store import LocalVectorStore


def test_tokenize_chinese_bigrams():
    toks = tokenize("ETCH-01 射频功率漂移")
    assert "etch" in toks and "01" in toks
    assert "射频" in toks and "频功" in toks


def test_bm25_keyword_ranking():
    idx = BM25Index()
    docs = [
        "SOP 通用安全注意事项, 进入维修模式前必须 LOTO 上锁挂牌",
        "E0010 告警码处理: 射频功率漂移时先暂停进片, 检查 Match Network",
        "每班检查干泵油位与 Chiller 水温",
    ]
    idx.build(docs)
    hits = idx.search("E0010 射频功率漂移", 3)
    assert hits and hits[0][0] == 1  # 命中关键词的文档排第一
    assert idx.search("LOTO", 1)[0][0] == 0


def _with_tmp_store():
    tmp = Path(tempfile.mkdtemp()) / "vs"
    store = LocalVectorStore(tmp)
    emb = MockEmbedder()
    texts = [
        ("sop.md", "腔压越限 C2201 处置: 检查 Throttle Valve 开度反馈, 做 Leak Check"),
        ("faq.md", "良率下降先查 SPC 趋势, 再反查机台与 particle 数据"),
    ]
    vecs, metas = [], []
    for src, t in texts:
        v = emb.embed_one(t)
        vecs.append(v)
        metas.append({"source": src, "text": t})
    store.add(vecs, metas)
    return store


def test_hybrid_retrieval_merges_sources():
    store = _with_tmp_store()
    orig_get_store, orig_bm25_len = pipeline.get_store, pipeline._bm25_len
    orig_bm25 = pipeline._bm25
    try:
        pipeline.get_store = lambda: store
        pipeline._bm25_len = -1  # 强制重建 BM25
        context, sources = pipeline._retrieve("C2201 腔压越限怎么处理")
        assert context is not None
        assert any(s["source"] == "sop.md" for s in sources)
        assert len(sources) <= 5
        # 精确关键词文档应因 BM25 加权而排到前列
        assert sources[0]["source"] == "sop.md"
    finally:
        pipeline.get_store = orig_get_store
        pipeline._bm25_len = orig_bm25_len
        pipeline._bm25 = orig_bm25


def test_empty_store_returns_none():
    tmp = Path(tempfile.mkdtemp()) / "vs2"
    store = LocalVectorStore(tmp)
    orig_get_store = pipeline.get_store
    try:
        pipeline.get_store = lambda: store
        context, sources = pipeline._retrieve("任何问题")
        assert context is None and sources == []
    finally:
        pipeline.get_store = orig_get_store


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
