import React from "react";
import { useAlarms } from "../hooks/useAlarms";

/** 铃铛 + 通知面板 + 应用内横幅 (自包含: 轮询/去重/桌面气泡都在 useAlarms) */
export default function NotificationCenter({ go, enabled = true }: { go: (v: string) => void; enabled?: boolean }) {
  const { notifs, unread, markAllRead, toasts } = useAlarms(enabled);
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const onDown = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, []);

  const LEVEL_TONE: Record<string, string> = {
    CRITICAL: "bg-[#FF453A] text-white", ALARM: "bg-[#FF9500] text-white",
    WARN: "bg-[#FFD60A]/30 text-[#B58A00]",
  };

  return (
    <>
      <div ref={ref} className="relative">
        <button type="button" className="tb-icon relative" title="告警通知"
          onClick={() => { setOpen(o => !o); if (open) markAllRead(); }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.7 21a2 2 0 0 1-3.4 0" />
          </svg>
          {unread > 0 && (
            <span className="absolute -top-1 -right-1 min-w-[15px] h-[15px] px-[3px] rounded-full
              bg-[#FF453A] text-white text-[9.5px] font-bold grid place-items-center leading-none">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
        {open && (
          <div className="absolute right-0 top-[30px] w-[360px] rounded-[14px] shadow-float z-50
            bg-white dark:bg-[#1C1C1E] border border-black/10 dark:border-white/10 overflow-hidden
            animate-[pop_.18s_ease-ios]">
            <div className="px-4 py-2.5 border-b border-black/5 dark:border-white/10 flex items-center">
              <span className="text-[13px] font-bold flex-1">告警通知</span>
              {unread > 0 && <button className="text-[11.5px] text-[#0A84FF]" onClick={markAllRead}>全部已读</button>}
            </div>
            <div className="max-h-[320px] overflow-y-auto">
              {notifs.length === 0 && (
                <div className="px-4 py-8 text-center text-[13px] text-ios-label2">暂无告警通知 🎉</div>
              )}
              {[...notifs].reverse().map(n => (
                <div key={n.id} onClick={() => go("tasks")}
                  className={`px-4 py-2.5 border-b border-black/5 dark:border-white/5 cursor-pointer
                    hover:bg-black/[.03] dark:hover:bg-white/[.05] ${!n.read ? "bg-[#0A84FF]/[.04]" : ""}`}>
                  <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${LEVEL_TONE[n.level] || ""}`}>{n.level}</span>
                    <span className="text-[12.5px] font-semibold">{n.eqp_id}</span>
                    <span className="ml-auto text-[10.5px] text-ios-label2">{n.dt}</span>
                    {!n.read && <span className="w-1.5 h-1.5 rounded-full bg-[#0A84FF]" />}
                  </div>
                  <div className="text-[12.5px] mt-0.5 truncate">{n.message}</div>
                </div>
              ))}
            </div>
            <button className="w-full py-2 text-[12px] text-[#0A84FF] hover:bg-black/[.03]"
              onClick={() => { setOpen(false); go("tasks"); }}>
              打开任务中心 →
            </button>
          </div>
        )}
      </div>

      {/* 应用内横幅 (网页预览降级用; 桌面端走系统气泡) */}
      <div className="fixed right-4 top-[48px] z-[60] space-y-2">
        {toasts.map(t => (
          <div key={t.id} className={`px-4 py-3 rounded-[12px] shadow-float text-[13px] w-[320px]
            animate-[pop_.2s_ease-ios] ${t.level === "CRITICAL"
              ? "bg-[#FF453A] text-white" : "bg-[#FF9500] text-white"}`}>
            <div className="font-bold">{t.level} · {t.eqp_id}</div>
            <div className="opacity-90 mt-0.5">{t.message}</div>
          </div>
        ))}
      </div>
    </>
  );
}
