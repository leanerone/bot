import React, { useEffect, useState } from "react";
import { Me, getJSON, Health } from "./api";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Knowledge from "./pages/Knowledge";
import Data from "./pages/Data";
import Tasks from "./pages/Tasks";
import Settings from "./pages/Settings";

type View = "home" | "chat" | "kb" | "data" | "tasks" | "settings";

const NAV: { key: View; icon: string; label: string; adminOnly?: boolean }[] = [
  { key: "home", icon: "🏠", label: "工作台" },
  { key: "chat", icon: "💬", label: "AI 对话" },
  { key: "kb", icon: "📚", label: "知识库" },
  { key: "data", icon: "📊", label: "数据台" },
  { key: "tasks", icon: "🛎️", label: "任务中心" },
  { key: "settings", icon: "⚙️", label: "设置" },
];

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [view, setView] = useState<View>("home");
  const [health, setHealth] = useState<Health | null>(null);
  const [dark, setDark] = useState(localStorage.getItem("fabbot.dark") === "1");
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("fabbot.dark", dark ? "1" : "0");
    (window as any).__themeChanged?.();
  }, [dark]);

  const refreshHealth = () => getJSON<Health>("/api/health").then(setHealth).catch(() => setHealth(null));

  useEffect(() => {
    getJSON<{ user: Me }>("/api/auth/me")
      .then(r => { setMe(r.user); refreshHealth(); })
      .catch(() => setMe(null))
      .finally(() => setAuthChecked(true));
  }, []);

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    setMe(null);
  };

  if (!authChecked) return <div className="h-full grid place-items-center text-ios-label2 text-[13px]">加载中…</div>;
  if (!me) return <Login onLogin={u => { setMe(u); refreshHealth(); }} />;

  const admin = me.role === "admin";
  const nav = NAV.filter(n => !n.adminOnly || admin);

  return (
    <div className="h-full flex">
      {/* ── 毛玻璃侧边栏 ── */}
      <aside className={`w-[228px] shrink-0 flex flex-col backdrop-blur-2xl
        bg-white/70 dark:bg-[#161618]/80 border-r border-black/10 dark:border-white/10
        transition-all duration-200 ease-ios ${collapsed ? "w-[64px]" : ""}`}>
        <div className={`pt-[44px] pb-3 ${collapsed ? "px-3" : "px-4"} flex items-center gap-2`}>
          <span className="text-[22px]">⚙️</span>
          {!collapsed && <div className="font-bold text-[16px]">Fab Bot<span className="ml-1.5 text-[11px] font-medium text-ios-label2">Desktop</span></div>}
        </div>
        <nav className="px-2.5 space-y-0.5">
          {nav.map(n => (
            <button key={n.key} onClick={() => setView(n.key)}
              className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-[10px] text-[14px] font-medium
                transition-colors duration-150 ${view === n.key
                  ? "bg-[#0A84FF] text-white shadow-sm"
                  : "hover:bg-black/5 dark:hover:bg-white/10 text-current"}`}>
              <span className="text-[16px]">{n.icon}</span>
              {!collapsed && <span>{n.label}</span>}
            </button>
          ))}
        </nav>
        <div className="flex-1" />
        {!collapsed && (
          <div className="mx-3 mb-2 p-3 rounded-[12px] bg-black/[.04] dark:bg-white/[.06] text-[12px] space-y-1">
            <Row k="模型" v={health ? (health.llm.mock ? "Mock 演示" : health.llm.model) : "离线"} />
            <Row k="知识库" v={health ? `${health.kb_chunks} 片段` : "–"} />
            <Row k="版本" v={health ? health.version : "–"} />
          </div>
        )}
        <div className={`mx-3 mb-3 p-2.5 rounded-[12px] bg-black/[.04] dark:bg-white/[.06] flex items-center gap-2`}>
          <span className="w-7 h-7 rounded-full bg-[#0A84FF] text-white grid place-items-center text-[12px] font-bold shrink-0">
            {(me.display_name || me.username).slice(0, 1)}
          </span>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <div className="text-[12.5px] font-semibold truncate">{me.display_name || me.username}</div>
              <div className="text-[10.5px] text-ios-label2">{me.role}</div>
            </div>
          )}
          {!collapsed && <button onClick={logout} className="text-[11px] text-ios-label2 hover:text-[#FF453A] shrink-0">退出</button>}
        </div>
        <button onClick={() => setCollapsed(!collapsed)}
          className="absolute bottom-1 left-1/2 -translate-x-1/2 text-[11px] text-ios-label2 hover:text-current pb-1">
          {collapsed ? "»" : "«"}
        </button>
      </aside>

      {/* ── 内容区 ── */}
      <main className="flex-1 min-w-0 flex flex-col">
        {view === "home" && <Home me={me} health={health} go={setView} />}
        {view === "chat" && <Chat me={me} />}
        {view === "kb" && <Knowledge me={me} />}
        {view === "data" && <Data me={me} />}
        {view === "tasks" && <Tasks me={me} />}
        {view === "settings" && <Settings me={me} health={health} dark={dark} setDark={setDark} refreshHealth={refreshHealth} />}
      </main>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return <div className="flex justify-between gap-2"><span className="text-ios-label2">{k}</span>
    <span className="truncate max-w-[110px] font-medium">{v}</span></div>;
}

export { NAV };
