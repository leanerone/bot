"""告警轮询守护: 定时扫描只读告警数据, 汇总后推送群机器人 (P3 路线图的主动服务原型)。

config.yaml -> watcher:
  enabled: false                 # 默认关闭; 试点确认推送内容后再开
  interval_minutes: 10
  levels: [ALARM, CRITICAL]      # 推送哪些级别
  platform: wechat               # wechat | dingtalk | both | none(仅审计)

设计:
- 守护线程, app 启动时 start_if_enabled() 拉起, 关闭时 stop()
- 状态持久化 data/watcher_state.json (last_run), 服务重启不重推旧告警
- 推送内容与轮询动作均落审计
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from app.config import abs_path, cfg


def build_summary(alarms: List[dict]) -> str:
    """告警列表 -> 推送文案 (纯函数, 便于单测)。"""
    if not alarms:
        return ""
    lines = [f"未处理告警 {len(alarms)} 条:"]
    for a in alarms[:10]:
        lines.append(
            f"· [{a.get('level', '?')}] {a.get('eqp_id', '?')} "
            f"{a.get('code', '')} {a.get('message', '')} @ {a.get('dt', '')}"
        )
    if len(alarms) > 10:
        lines.append(f"… 其余 {len(alarms) - 10} 条请到 Fab Bot 查看")
    return "\n".join(lines)


class AlarmWatcher(threading.Thread):
    def __init__(self, adapter, sender: Callable[[str], None],
                 levels: Optional[List[str]] = None,
                 state_file: Optional[Path] = None,
                 interval_minutes: Optional[int] = None):
        super().__init__(daemon=True, name="alarm-watcher")
        self.adapter = adapter
        self.sender = sender
        self.levels = set(levels or cfg("watcher.levels", ["ALARM", "CRITICAL"]))
        self._state_file = Path(state_file) if state_file else abs_path("data/watcher_state.json")
        self._interval = int((interval_minutes if interval_minutes is not None
                              else cfg("watcher.interval_minutes", 10)) * 60)
        self._stop = threading.Event()

    # ── 状态 ──

    def _last_run(self) -> float:
        try:
            return float(json.loads(self._state_file.read_text(encoding="utf-8"))["last_run"])
        except Exception:
            return time.time() - 3600  # 首次运行回看 1 小时

    def _save_run(self, ts: float) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps({"last_run": ts,
                        "updated": datetime.now().isoformat(timespec="seconds")}),
            encoding="utf-8",
        )

    # ── 轮询 ──

    def check_once(self) -> int:
        """执行一轮检查, 返回推送条数 (纯逻辑, 单测直接调用)。"""
        since_hours = max(1, int((time.time() - self._last_run()) / 3600) + 1)
        alarms = [a for a in self.adapter.get_alarms(hours=since_hours, only_open=True)
                  if a.get("level") in self.levels]
        self._save_run(time.time())
        if not alarms:
            return 0
        text = build_summary(alarms)
        if self.sender and text:
            self.sender(text)
        return len(alarms)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self.check_once()
            except Exception as exc:  # 守护线程不允许挂掉
                print(f"[watcher] 轮询异常: {exc}")
            self._stop.wait(self._interval)

    def stop(self) -> None:
        self._stop.set()


def _default_sender():
    from app.config import cfg as _cfg

    platform = _cfg("watcher.platform", "wechat")
    if platform == "none":
        return lambda text: None
    from app.notify import webhook
    return lambda text: webhook.send(platform, text)


def start_if_enabled(adapter=None) -> Optional[AlarmWatcher]:
    """config watcher.enabled=true 时拉起守护线程, 否则返回 None。"""
    if not cfg("watcher.enabled", False):
        return None
    if adapter is None:
        from app.adapters.mock_mes import MockMESAdapter
        adapter = MockMESAdapter()
    w = AlarmWatcher(adapter, _default_sender())
    w.start()
    print(f"[watcher] 告警轮询已启动 (间隔 {w._interval // 60} 分钟, 级别 {sorted(w.levels)})")
    return w
