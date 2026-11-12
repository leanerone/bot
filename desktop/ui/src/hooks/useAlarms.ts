import { useCallback, useEffect, useRef, useState } from "react";
import { getJSON } from "../api";

export interface Notif {
  id: number; level: string; eqp_id: string; message: string; dt: string; read: boolean;
}

const LS_NOTIFS = "fabbot.notifs";
const LS_CURSOR = "fabbot.alarmCursor";

function load(): Notif[] {
  try { return JSON.parse(localStorage.getItem(LS_NOTIFS) || "[]"); } catch { return []; }
}
function save(list: Notif[]) {
  localStorage.setItem(LS_NOTIFS, JSON.stringify(list.slice(-50)));
}

/**
 * 告警通知轮询: 每 60s 用 id 游标取新增 CRITICAL/ALARM 告警。
 * 新增 → 未读列表 + 桌面气泡 (WebView2 WebMessage) 或应用内横幅 (网页预览)。
 * 首次运行只同步游标, 不把历史告警当"新"通知轰炸。
 */
export function useAlarms(enabled: boolean, intervalMs = 60000) {
  const [notifs, setNotifs] = useState<Notif[]>(load);
  const [cursor, setCursor] = useState<number>(() => Number(localStorage.getItem(LS_CURSOR) || 0));
  const [toasts, setToasts] = useState<Notif[]>([]);
  const first = useRef(!localStorage.getItem(LS_CURSOR));
  const wv = (window as any).chrome?.webview;

  const pushToast = useCallback((n: Notif) => {
    const action = `toast:${n.level}|${n.eqp_id}|${n.message}`;
    if (wv?.postMessage) { wv.postMessage(action); return; }
    setToasts(t => [...t.slice(-2), n]);
    window.setTimeout(() => setToasts(t => t.filter(x => x.id !== n.id)), 6000);
  }, []);

  const poll = useCallback(async () => {
    if (document.hidden) return;
    try {
      const r = await getJSON<{ alarms: Notif[]; last_id: number }>(
        `/api/tasks/alarms/since?after_id=${cursor}&levels=CRITICAL,ALARM`);
      if (first.current) {           // 首次: 只同步游标
        first.current = false;
        setCursor(r.last_id);
        localStorage.setItem(LS_CURSOR, String(r.last_id));
        return;
      }
      if (r.alarms.length) {
        setNotifs(prev => {
          const next = [...prev, ...r.alarms.map(a => ({ ...a, read: false }))].slice(-50);
          save(next);
          return next;
        });
        if (document.hidden === false) for (const n of r.alarms) pushToast(n);
      }
      if (r.last_id > cursor) { setCursor(r.last_id); localStorage.setItem(LS_CURSOR, String(r.last_id)); }
    } catch { /* 离线/未登录静默 */ }
  }, [cursor, enabled, pushToast, wv]);

  useEffect(() => {
    if (!enabled) return;
    poll();
    const t = window.setInterval(poll, intervalMs);
    const onVisible = () => { if (!document.hidden) poll(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => { window.clearInterval(t); document.removeEventListener("visibilitychange", onVisible); };
  }, [enabled, poll, intervalMs]);

  const markAllRead = useCallback(() => {
    setNotifs(prev => { const next = prev.map(n => ({ ...n, read: true })); save(next); return next; });
  }, []);

  const unread = notifs.filter(n => !n.read).length;
  return { notifs, unread, markAllRead, toasts, refresh: poll };
}
