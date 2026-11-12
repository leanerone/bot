import React from "react";

/**
 * 统一线性图标集：与桌面客户端的菜单栏 / 侧栏同一套笔画粗细，
 * 替换原先大小不一、颜色不一的 emoji。
 */
const PATHS: Record<string, React.ReactNode> = {
  panel: <><rect x="3" y="4" width="18" height="16" rx="2.5" /><path d="M9.5 4v16" /></>,
  search: <><circle cx="10.8" cy="10.8" r="6.3" /><path d="m15.4 15.4 4.2 4.2" /></>,
  sliders: <><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  home: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.6" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.6" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.6" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.6" /></>,
  chat: <><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H8l-4 2.2.9-3.6A7.5 7.5 0 1 1 20 11.5Z" /><path d="M8.5 11.5h7" /></>,
  book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15.5H6.5A2.5 2.5 0 0 0 4 21V5.5Z" /><path d="M4 18.5A2.5 2.5 0 0 1 6.5 16H20" /><path d="M8 7.5h8" /></>,
  database: <><ellipse cx="12" cy="5.5" rx="7.5" ry="2.8" /><path d="M4.5 5.5v6c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-6" /><path d="M4.5 11.5v6c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-6" /></>,
  bell: <><path d="M18 9a6 6 0 0 0-12 0c0 5-2 6-2 6h16s-2-1-2-6Z" /><path d="M10 19a2 2 0 0 0 4 0" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1-2 2-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5v.2h-3v-.2a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1-2-2 .1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H6v-3h.2a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1 2-2 .1.1a1.6 1.6 0 0 0 1.8.3h.1a1.6 1.6 0 0 0 1-1.5V5h3v.2a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1 2 2-.1.1a1.6 1.6 0 0 0-.3 1.8v.1a1.6 1.6 0 0 0 1.5 1h.2v3h-.2a1.6 1.6 0 0 0-1.5 1Z" /></>,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5.3l3.4 2" /></>,
  chevron: <path d="m6 9 6 6 6-6" />,
  refresh: <><path d="M20 11a8 8 0 1 0-2.3 6" /><path d="M20 4.5V11h-6" /></>,
  power: <><path d="M12 3.5v8" /><path d="M7.2 6.4a7.5 7.5 0 1 0 9.6 0" /></>,
  check: <path d="m5 12.5 4.5 4.5L19 7" />,
  help: <><circle cx="12" cy="12" r="8.5" /><path d="M9.7 9.3a2.4 2.4 0 1 1 3.4 2.2c-.8.4-1.1.9-1.1 1.8" /><path d="M12 16.7h.01" /></>,
  external: <><path d="M13 5h6v6" /><path d="m19 5-8.5 8.5" /><path d="M18 14v4.5A1.5 1.5 0 0 1 16.5 20h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6H10" /></>,
  logout: <><path d="M14 4h3.5A1.5 1.5 0 0 1 19 5.5v13a1.5 1.5 0 0 1-1.5 1.5H14" /><path d="M9 8l-4 4 4 4M5 12h9" /></>,
  keyboard: <><rect x="2.5" y="6" width="19" height="12" rx="2" /><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 13.5h.01M10 13.5h.01M14 13.5h.01M18 13.5h.01M8.5 16h7" /></>,
  info: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 8h.01" /></>,
  chip: <><rect x="6" y="6" width="12" height="12" rx="2.5" /><rect x="9.5" y="9.5" width="5" height="5" rx="1" /><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M18.8 5.2l-1.4 1.4M6.6 17.4l-1.4 1.4" /></>,
  moon: <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />,
  window: <><rect x="3" y="4.5" width="18" height="15" rx="2" /><path d="M3 9h18M7 6.7h.01M9.8 6.7h.01" /></>,
  sparkle: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" /><path d="m18.5 16 .7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7.7-2Z" /></>,
  file: <><path d="M6 3h7l5 5v12.5A1.5 1.5 0 0 1 16.5 22h-10A1.5 1.5 0 0 1 5 20.5v-16A1.5 1.5 0 0 1 6.5 3Z" /><path d="M13 3v5h5M8.5 13h7M8.5 17h5" /></>,
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18, className = "" }: {
  name: IconName; size?: number; className?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
      className={className} aria-hidden focusable="false">
      {PATHS[name]}
    </svg>
  );
}
