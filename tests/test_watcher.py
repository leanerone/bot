"""告警轮询守护测试 (假适配器 + 假发送器, 不碰网络)。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.watcher.alarm_watcher import AlarmWatcher, build_summary


class FakeAdapter:
    def __init__(self, alarms):
        self.alarms = alarms

    def get_alarms(self, hours=24, only_open=True):
        return self.alarms


def _make(alarms, state_file):
    sent = []
    w = AlarmWatcher(FakeAdapter(alarms), lambda text: sent.append(text),
                     levels={"ALARM", "CRITICAL"}, state_file=Path(state_file))
    return w, sent


def test_build_summary_format():
    text = build_summary([
        {"level": "CRITICAL", "eqp_id": "ETCH-02", "code": "C2201",
         "message": "腔压越限", "dt": "2026-11-05 01:00"},
    ])
    assert text.startswith("未处理告警 1 条:")
    assert "[CRITICAL] ETCH-02 C2201 腔压越限" in text
    assert build_summary([]) == ""


def test_summary_caps_at_10():
    alarms = [{"level": "WARN", "eqp_id": f"E-{i}", "code": "X", "message": "m", "dt": "t"}
              for i in range(15)]
    text = build_summary(alarms)
    assert "其余 5 条" in text and text.count("· [") == 10


def test_check_once_pushes_matching_levels():
    w, sent = _make([
        {"level": "CRITICAL", "eqp_id": "ETCH-02", "code": "C2201", "message": "腔压", "dt": "t1"},
        {"level": "WARN", "eqp_id": "CMP-01", "code": "X", "message": "m", "dt": "t2"},  # WARN 不推
    ], Path(tempfile.mkdtemp()) / "state.json")
    n = w.check_once()
    assert n == 1 and len(sent) == 1 and "ETCH-02" in sent[0]
    # 第二轮: last_run 已更新, 假适配器仍返回同样数据但时间窗从当前起算 —— 依然推送 (假数据无时间过滤)
    assert w.check_once() == 1


def test_check_once_silent_when_empty():
    w, sent = _make([], Path(tempfile.mkdtemp()) / "s2.json")
    assert w.check_once() == 0 and sent == []
    assert w._last_run() > 0  # 状态已更新


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
