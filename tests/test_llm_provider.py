"""E0: LLM Provider 层 —— azure / azure-classic / openai 三档 + 断网降级。"""
from __future__ import annotations


import httpx

from app.llm import client as llm_client
from app.llm.client import DegradedLLM, MockLLM, OpenAICompatLLM


def _capture(monkeypatch, handler):
    """拦截 httpx 模块级 post, 记录请求并返回 handler 的响应。"""
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        return handler(url, json, headers)

    monkeypatch.setattr(llm_client.httpx, "post", fake_post)
    return calls


def _ok_response(content: str = "hi"):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", "http://test"),
    )


def test_openai_provider_bearer(monkeypatch):
    """默认 openai provider: Bearer 头, 零回归。"""
    calls = _capture(monkeypatch, lambda u, j, h: _ok_response())
    llm = OpenAICompatLLM("http://vllm:8000/v1", "sk-test", "qwen")
    assert llm.chat([{"role": "user", "content": "hi"}]) == "hi"
    assert calls[0]["url"] == "http://vllm:8000/v1/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer sk-test"


def test_azure_v1_apikey_header(monkeypatch):
    """azure provider: api-key 头 + v1 兼容端点。"""
    calls = _capture(monkeypatch, lambda u, j, h: _ok_response())
    llm = OpenAICompatLLM(
        "https://res.openai.azure.com/openai/v1", "az-key", "gpt-4o-mini", provider="azure"
    )
    assert llm.chat([{"role": "user", "content": "hi"}]) == "hi"
    assert calls[0]["url"] == "https://res.openai.azure.com/openai/v1/chat/completions"
    assert calls[0]["headers"]["api-key"] == "az-key"
    assert "Authorization" not in calls[0]["headers"]


def test_azure_classic_deployment_url(monkeypatch):
    """azure-classic: deployment URL + api-version + api-key 头。"""
    calls = _capture(monkeypatch, lambda u, j, h: _ok_response())
    llm = OpenAICompatLLM(
        "https://res.openai.azure.com",
        "az-key",
        "gpt-4o-mini",
        provider="azure-classic",
        api_version="2024-10-21",
    )
    llm.chat([{"role": "user", "content": "hi"}])
    assert calls[0]["url"] == (
        "https://res.openai.azure.com/openai/deployments/gpt-4o-mini"
        "/chat/completions?api-version=2024-10-21"
    )
    assert calls[0]["headers"]["api-key"] == "az-key"
    assert calls[0]["json"]["model"] == "gpt-4o-mini"


def test_fallback_mock_on_error(monkeypatch):
    """云端不可达: DegradedLLM 降级 Mock 并首行标注。"""
    def fail_handler(u, j, h):
        raise httpx.ConnectError("refused")

    _capture(monkeypatch, fail_handler)
    real = OpenAICompatLLM("http://unreachable:9/v1", "k", "m")
    deg = DegradedLLM(real, MockLLM())
    out = deg.chat([{"role": "user", "content": "告警"}])
    assert out.startswith("⚠️")
    assert deg.degraded is True
    # 流式同样降级
    chunks = list(deg.chat_stream([{"role": "user", "content": "hi"}]))
    assert "".join(chunks).startswith("⚠️")


def test_fallback_transparent_on_success(monkeypatch):
    """云端正常: 降级层透传, 不注入标注。"""
    calls = _capture(monkeypatch, lambda u, j, h: _ok_response("真回答"))
    deg = DegradedLLM(
        OpenAICompatLLM("http://ok:1/v1", "k", "m", provider="azure"), MockLLM()
    )
    out = deg.chat([{"role": "user", "content": "hi"}])
    assert out == "真回答"
    assert deg.degraded is False
    assert calls[0]["headers"]["api-key"] == "k"


def test_get_llm_reads_provider_config():
    """get_llm 组装: provider/api_version 传入, fallback_mock 包装。"""
    llm = llm_client.get_llm()
    # config.yaml 当前 mock=true → MockLLM
    assert isinstance(llm, MockLLM)
    raw = OpenAICompatLLM("u", "k", "m")
    assert raw._endpoint() == "u/chat/completions"
