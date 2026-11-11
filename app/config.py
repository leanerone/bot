"""全局配置加载。

从项目根目录的 config.yaml 读取, 提供 cfg("a.b.c", default) 点路径取值;
所有相对路径统一相对项目根目录解析, 与启动时的工作目录无关。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import os

import yaml

# PyInstaller sidecar 模式: FABBOT_ROOT 环境变量指定可写数据根目录
ROOT = Path(os.environ.get("FABBOT_ROOT") or Path(__file__).resolve().parent.parent)


def load_config(path: Optional[str] = None) -> dict:
    config_file = Path(path) if path else ROOT / "config.yaml"
    with open(config_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


CFG = load_config()


def cfg(key_path: str, default: Any = None) -> Any:
    """按点路径取配置, 如 cfg("llm.mock") / cfg("rag.top_k", 5)。"""
    node: Any = CFG
    for part in key_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def abs_path(p: str) -> Path:
    """相对路径 -> 相对项目根目录的绝对路径。"""
    path = Path(p)
    return path if path.is_absolute() else ROOT / path
