"""统一日志: 替代散落 print (无级别/无轮转, PyInstaller 窗口模式下 print 丢失)。

config.yaml -> logging.level (INFO/DEBUG/...) / logging.file (相对项目根, 空=仅控制台)。
所有模块经 get_logger(__name__) 取 "fabbot.*" 子日志器, 统一受根配置控制。
"""
from __future__ import annotations

import logging
import logging.handlers

from app.config import abs_path, cfg

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    level = getattr(logging, str(cfg("logging.level", "INFO")).upper(), logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger("fabbot")
    root.setLevel(level)
    root.handlers.clear()
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    log_file = cfg("logging.file", "")
    if log_file:
        p = abs_path(log_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            p, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"fabbot.{name}")
