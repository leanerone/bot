"""LLM 网关。

统一走 OpenAI 兼容的 /chat/completions 接口, 因此 vLLM / Ollama / 各类推理服务
都可直接对接, 只需修改 config.yaml 的 base_url 与 model, 业务代码零改动。

config.llm.mock = true 时使用内置 MockLLM: 无 GPU、无推理服务的环境也能
跑通全流程 (回答为占位内容, 仅用于演示链路)。
"""
from __future__ import annotations

import json
import re
import time
from typing import Iterator, List, Optional

import httpx

from app.config import cfg


class LLMError(RuntimeError):
    """LLM 服务不可用或调用失败。"""


def _get_message(messages: List[dict], role: str) -> str:
    for m in reversed(messages):
        if m.get("role") == role:
            return m.get("content", "")
    return ""


class OpenAICompatLLM:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "EMPTY"
        self.model = model
        self.timeout = timeout

    def chat(self, messages: List[dict], temperature: Optional[float] = None) -> str:
        payload = {"model": self.model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM 服务不可用 ({self.base_url}): {exc}") from exc
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"LLM 返回格式异常: {resp.text[:200]}") from exc

    def chat_stream(self, messages: List[dict], temperature: Optional[float] = None) -> Iterator[str]:
        """流式生成: 逐段产出文本增量 (OpenAI 兼容 stream=true 协议)。"""
        payload = {"model": self.model, "messages": messages, "stream": True}
        if temperature is not None:
            payload["temperature"] = temperature
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            delta = json.loads(data)["choices"][0].get("delta", {})
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                        if delta.get("content"):
                            yield delta["content"]
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM 服务不可用 ({self.base_url}): {exc}") from exc


class MockLLM:
    """离线演示用: 识别 prompt 类型, 返回占位回答。"""

    def chat(self, messages: List[dict], temperature: Optional[float] = None) -> str:
        system = _get_message(messages, "system")
        user = _get_message(messages, "user")
        if "检索到的知识库片段" in system:
            return self._rag_answer(system)
        if "SQL 生成器" in system:
            return self._sql_answer(user)
        return f"(Mock 回答) 已收到问题: {user[:80]}"

    @staticmethod
    def _rag_answer(system: str) -> str:
        chunks = re.findall(r"\[(\d+)\] 来源: (.+)\n(.+?)(?=\n\n\[\d+\]|\Z)", system, re.S)
        if not chunks:
            return "知识库中未找到相关内容。"
        ids = [c[0] for c in chunks[:2]]
        snippet = chunks[0][2].strip().replace("\n", " ")[:120]
        return (
            f"根据知识库 [{'、'.join(ids)}] 中的内容: {snippet}……\n\n"
            "(当前为 Mock 模式; 配置真实 LLM 后将输出完整自然语言回答)"
        )

    @staticmethod
    def _sql_answer(question: str) -> str:
        q = question.lower()
        rules = [
            (r"平均(良率|合格率|die)|良率.*平均", "SELECT product, AVG(die_yield) AS avg_yield FROM yield_daily WHERE dt >= DATE('now', 'localtime', '-7 day') GROUP BY product ORDER BY avg_yield DESC LIMIT 20"),
            (r"几台|多少台|机台数量|数量.*机台", "SELECT eqp_group, COUNT(*) AS cnt FROM eqp WHERE status = 'DOWN' GROUP BY eqp_group ORDER BY cnt DESC LIMIT 20"),
            (r"良率|合格率", "SELECT dt, product, die_yield FROM yield_daily ORDER BY dt DESC LIMIT 10"),
            (r"告警|报警|alarm", "SELECT dt, eqp_id, level, code, message FROM alarms WHERE handled = 0 ORDER BY dt DESC LIMIT 10"),
            (r"机台|设备|eqp", "SELECT eqp_id, eqp_group, vendor, status FROM eqp ORDER BY eqp_id LIMIT 20"),
            (r"批次|lot|在制|wip", "SELECT lot_id, product, layer, qty FROM wip ORDER BY lot_id LIMIT 20"),
        ]
        for pattern, sql in rules:
            if re.search(pattern, q):
                return sql
        return "SELECT eqp_id, status FROM eqp LIMIT 10"

    def chat_stream(self, messages: List[dict], temperature: Optional[float] = None) -> Iterator[str]:
        """Mock 流式: 把整段回答切片输出, 模拟打字机效果。"""
        text = self.chat(messages, temperature)
        for i in range(0, len(text), 8):
            yield text[i : i + 8]
            time.sleep(0.02)


def get_llm():
    if cfg("llm.mock", True):
        return MockLLM()
    return OpenAICompatLLM(
        base_url=cfg("llm.base_url", "http://127.0.0.1:8000/v1"),
        api_key=cfg("llm.api_key", "EMPTY"),
        model=cfg("llm.model", "Qwen2.5-32B-Instruct-AWQ"),
        timeout=float(cfg("llm.timeout", 120)),
    )
