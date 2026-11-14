"""D/E 组测试: Agent 循环 / 技能执行器 / rerank / Notes 增量 / Word 导出 / MCP envelope。"""
from __future__ import annotations

import json

import pytest

from app.agent import loop as agent_loop
from app.skillhub import runner as skill_runner


# ── D3: Agent 循环 ──

def test_agent_alarm_path():
    r = agent_loop.run_agent("最近未处理的告警有哪些", user="t")
    assert any(s["tool"] == "alarms_open" and s["ok"] for s in r["steps"])
    assert "未处理告警" in r["answer"]


def test_agent_kb_path_has_sources():
    r = agent_loop.run_agent("射频功率漂移怎么处理", user="t")
    assert any(s["tool"] == "kb_search" and s["ok"] for s in r["steps"])
    assert len(r["sources"]) > 0


def test_agent_sql_and_shift_paths():
    r = agent_loop.run_agent("最近一周 P1234 的平均良率", user="t")
    assert any(s["tool"] == "sql_query" and s["ok"] for s in r["steps"])
    r2 = agent_loop.run_agent("生成交班报告", user="t")
    assert any(s["tool"] == "shift_report" and s["ok"] for s in r2["steps"])


def test_agent_unknown_tool_rejected():
    r = agent_loop.call_tool("rm_rf_slash", {})
    assert not r["ok"] and "不在白名单" in r["error"]


def test_agent_on_step_callback():
    events = []
    agent_loop.run_agent("最近未处理的告警", user="t", on_step=events.append)
    assert events and events[0]["type"] == "agent_step" and "tool" in events[0]


def test_agent_write_tool_needs_confirm():
    """预留: requires_confirm 工具无确认卡必须拒绝 (防过度代理)。"""
    spec = agent_loop.TOOLS["kb_search"]
    spec["requires_confirm"] = True
    try:
        r = agent_loop.call_tool("kb_search", {"query": "x"})
        assert not r["ok"] and r.get("confirm_required")
    finally:
        spec["requires_confirm"] = False


# ── D4: 技能执行器 ──

@pytest.mark.parametrize("name", ["rag", "text2sql", "alarm-watch"])
def test_skill_run_builtin(name):
    r = skill_runner.run_skill(name, user="t")
    assert r["ok"], r.get("error")


def test_skill_run_unknown():
    assert not skill_runner.run_skill("nope")["ok"]


# ── E1: rerank ──

def test_rerank_off_exact_boost():
    from app.rag.rerank import rerank_hits

    hits = [
        {"source": "CMP 研磨 SOP", "text": "腔压越限处理", "score": 0.03},
        {"source": "ETCH SOP", "text": "ETCH-02 的 E0010 射频功率漂移", "score": 0.02},
    ]
    out = rerank_hits("ETCH-02 的 E0010 告警怎么处理", hits, top_n=2)
    assert out[0]["source"].startswith("ETCH")


def test_rerank_never_raises(monkeypatch):
    from app.rag import rerank as rr

    monkeypatch.setattr(rr, "get_reranker", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    out = rr.rerank_hits("q", [{"source": "a", "text": "b", "score": 1.0}], top_n=1)
    assert out and out[0]["source"] == "a"


# ── B4: Word 导出 ──

def test_shift_docx_export():
    from app.services.shift_report import build_shift_report, export_docx

    data = export_docx(build_shift_report(12))
    assert data[:2] == b"PK" and len(data) > 5000


def test_shift_push_endpoint_contract():
    """推送端点: 未配置 webhook 时 400 (语义明确), 不裸抛。"""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    resp = client.post("/api/tasks/shift-report/push", json={"hours": 8})
    assert resp.status_code == 400  # teams webhook 未配置


# ── E2: 意图 smart (mock 走关键词) ──

def test_classify_smart_fallback_keyword():
    from app.api.intent import classify_smart

    assert classify_smart("最近未处理的告警")["intent"] == "sql"
    assert classify_smart("射频功率漂移怎么处理")["intent"] == "kb"


# ── E3: 历史压缩 ──

def test_compress_history_long():
    from app.llm.prompts import compress_history

    hist = []
    for i in range(14):
        hist += [{"role": "user", "content": f"问题 {i}"},
                 {"role": "assistant", "content": f"回答 {i}"}]
    out = compress_history(hist, keep_recent=6, max_turns=10)
    assert len(out) < len(hist) and out[0]["content"].startswith("[对话摘要]")


# ── D1: MCP envelope ──

def test_mcp_envelope_format():
    from mcp_server import _env, _kb_sources_impl

    ok = json.loads(_env(_kb_sources_impl))
    assert ok["ok"] is True and "sources" in ok["data"]
    err = json.loads(_env(lambda: (_ for _ in ()).throw(ValueError("bad"))))
    assert err["ok"] is False and "bad" in err["error"]


# ── B5: Notes 增量 ──

def test_notes_incremental_dedup_key():
    from app.adapters.hcl_notes import _existing_note_unids

    class FakeStore:
        metas = [{"source": "s", "text": "t", "notes_unid": "U1"},
                 {"source": "s", "text": "t2"}]

    assert _existing_note_unids(FakeStore()) == {"U1"}


def test_dominoclient_doclink():
    from app.adapters.hcl_notes import NoteDoc

    doc = NoteDoc(unid="ABC123", db_path="KB/process.nsf", subject="x")
    assert doc.doclink() == "notes://KB/process.nsf/ABC123"
