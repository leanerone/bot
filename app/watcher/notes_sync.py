"""B5: Notes 定时增量同步守护 (复用 alarm-watcher 的守护线程模式)。

config.yaml -> notes.sync.interval_minutes > 0 时启用; 拉取失败退回导出目录模式提示。
"""
from __future__ import annotations

import threading
from typing import Optional

from app.config import cfg


class NotesSyncDaemon(threading.Thread):
    def __init__(self, interval_minutes: Optional[int] = None):
        super().__init__(daemon=True, name="notes-sync")
        self._interval = int((interval_minutes if interval_minutes is not None
                              else cfg("notes.sync.interval_minutes", 0)) * 60)
        self._stop = threading.Event()
        self.last_result: dict = {}

    def sync_once(self) -> dict:
        """执行一轮增量同步 (纯逻辑, 单测直接调用)。失败不抛出, 记入 errors。"""
        from app.adapters.hcl_notes import ingest_notes_domino, ingest_notes_domino_multi

        mode = cfg("notes.mode", "export")
        if mode != "domino":
            return {"skipped": "notes.mode != domino"}
        multi = cfg("notes.databases") or []
        try:
            if multi:
                self.last_result = ingest_notes_domino_multi(multi)
            else:
                from app.api.routes import _notes_domino_client

                self.last_result = ingest_notes_domino(_notes_domino_client())
        except Exception as exc:  # noqa: BLE001 —— 守护线程不允许挂掉
            self.last_result = {"errors": [f"同步失败 (可退回导出目录模式): {exc}"]}
        return self.last_result

    def run(self) -> None:
        while not self._stop.is_set():
            self.sync_once()
            self._stop.wait(self._interval)

    def stop(self) -> None:
        self._stop.set()


def start_if_enabled() -> Optional[NotesSyncDaemon]:
    minutes = int(cfg("notes.sync.interval_minutes", 0) or 0)
    if minutes <= 0 or cfg("notes.mode", "export") != "domino":
        return None
    daemon = NotesSyncDaemon(minutes)
    daemon.start()
    return daemon
