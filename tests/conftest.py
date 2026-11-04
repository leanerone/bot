import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """限流器为进程内全局状态, 每个用例前后清空, 避免相互泄漏。"""
    from app.api.limits import _hits

    _hits.clear()
    yield
    _hits.clear()
