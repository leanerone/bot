import React, { useEffect, useState } from "react";
import { Me, getJSON, Health, SessionMeta } from "./api";
import Login from "./pages/Login";
import NotificationCenter from "./components/NotificationCenter";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import Knowledge from "./pages/Knowledge";
import Data from "./pages/Data";
import Tasks from "./pages/Tasks";
import Settings from "./pages/Settings";
import TitleBar, { GlassMode } from "./components/TitleBar";
import { Icon, IconName } from "./components/icons";
import { MenuItem, MenuPop, useMenuDismiss } from "./components/Menu";

type View = "home" | "chat" | "kb" | "data" | "tasks" | "settings";
type NavItem = { key: View; icon: IconName; label: string };

/* 与桌面客户端一致：主功能一组、运维一组、最近会话一组 */
const NAV_MAIN: NavItem[] = [
  { key: "chat", icon: "chat", label: "AI 对话" },
  { key: "home", icon: "home", label: "工作台" },
  { key: "kb", icon: "book", label: "知识库" },
  { key: "data", icon: "database", label: "数据查询" },
];
const NAV_OPS: NavItem[] = [
  { key: "tasks", icon: "bell", label: "告警值守" },
  { key: "settings", icon: "settings", label: "设置" },
];

let busyTimer: number | undefined;
function markGlassBusy() {
  const h = document.documentElement;
  h.classList.add("glass-busy");
  clearTimeout(busyTimer);
  busyTimer = window.setTimeout(() => h.classList.remove("glass-busy"), 220);
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [view, setView] = useState<View>("home");
  const [health, setHealth] = useState<Health | null>(null);
  const [dark, setDark] = useState(localStorage.getItem("fabbot.dark") === "1");
  const [glass, setGlass] = useState<GlassMode>(() => {
    const v = localStorage.getItem("fabbot.glass");
    return v === "off" || v === "eco" ? v : "on";
  });
  const [collapsed, setCollapsed] = useState(false);
  const [sessions, setSessions] = useState<SessionMeta[]>([]);
  const [openSession, setOpenSession] = useState<string | null>(null);
  const [brandOpen, setBrandOpen] = useState(false);
  const [brandPos, setBrandPos] = useState({ left: 12, top: 96 });

  useMenuDismiss(brandOpen, () => setBrandOpen(false), "side");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("fabbot.dark", dark ? "1" : "0");
    (window as any).__themeChanged?.();
    // 同步窗口/WebView2 底色，避免深色模式下缩放露出浅色块
    (window as any).chrome?.webview?.postMessage?.(dark ? "theme:dark" : "theme:light");
  }, [dark]);

  useEffect(() => {
    const h = document.documentElement;
    h.dataset.glass = glass;
    h.classList.toggle("glass-on", glass !== "off");
    localStorage.setItem("fabbot.glass", glass);
  }, [glass]);

  // 缩放窗口 / 切换页面时临时摘掉模糊层，优先保帧率
  useEffect(() => {
    const onResize = () => markGlassBusy();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  useEffect(() => { markGlassBusy(); }, [view]);

  // L4 指针高光：rAF 节流，每帧最多更新一张卡片
  useEffect(() => {
    if (glass === "off") return;
    let raf = 0;
    let pending: { el: HTMLElement; x: number; y: number } | null = null;
    const flush = () => {
      raf = 0;
      if (!pending) return;
      const { el, x, y } = pending;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--lx", `${x - r.left}px`);
      el.style.setProperty("--ly", `${y - r.top}px`);
      pending = null;
    };
    const onMove = (e: PointerEvent) => {
      const el = (e.target as HTMLElement | null)?.closest?.(".glass, .ios-card") as HTMLElement | null;
      if (!el) return;
      pending = { el, x: e.clientX, y: e.clientY };
      if (!raf) raf = requestAnimationFrame(flush);
    };
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      document.removeEventListener("pointermove", onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [glass]);

  const refreshHealth = () => getJSON<Health>("/api/health").then(setHealth).catch(() => setHealth(null));

  useEffect(() => {
    getJSON<{ user: Me }>("/api/auth/me")
      .then(r => { setMe(r.user); refreshHealth(); })
      .catch(() => setMe(null))
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    if (!me) return;
    getJSON<{ sessions: SessionMeta[] }>("/api/sessions")
      .then(r => setSessions(r.sessions)).catch(() => {});
  }, [me, view]);

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    setMe(null);
    setSessions([]);
  };

  const go = (v: string) => { setOpenSession(null); setView(v as View); };
  const goSession = (id: string) => { setOpenSession(id); setView("chat"); };

  const navBtn = (n: NavItem) => (
    <button key={n.key} type="button"
      className={`nav-item${view === n.key ? " is-active" : ""}`}
      title={collapsed ? n.label : undefined} onClick={() => go(n.key)}>
      <span className="nav-ic"><Icon name={n.icon} size={17} /></span>
      {!collapsed && <span className="nav-label">{n.label}</span>}
    </button>
  );

  const toggleBrand = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    setBrandPos({ left: Math.max(8, r.right - 228), top: r.bottom + 7 });
    setBrandOpen(v => !v);
  };

  const brandItems: MenuItem[] = [
    { label: "模型", hint: health ? (health.llm.mock ? "Mock 演示" : health.llm.model) : "–", disabled: true },
    { label: "知识库", hint: health ? `${health.kb_chunks} 片段` : "–", disabled: true },
    { label: "版本", hint: `V${health?.version || "4.2"}`, disabled: true },
    { label: "刷新服务状态", icon: "refresh", separator: true, onSelect: refreshHealth },
    { label: "打开设置", icon: "settings", onSelect: () => go("settings") },
  ];

  let body: React.ReactNode;
  if (!authChecked) {
    body = <div className="h-full grid place-items-center text-ios-label2 text-[13px]">加载中…</div>;
  } else if (!me) {
    body = <Login onLogin={u => { setMe(u); refreshHealth(); }} />;
  } else {
    body = (
      <div className="h-full flex">
        {/* ── 侧栏：品牌区 + 分组导航 + 最近会话 + 账号 ── */}
        <aside className={`app-sidebar relative shrink-0 flex flex-col glass-sidebar backdrop-blur-2xl
          bg-white/70 dark:bg-[#161618]/80
          transition-all duration-200 ease-ios ${collapsed ? "w-[68px] is-collapsed" : "w-[240px]"}`}>
          <span className="edge-divider" aria-hidden />

          <div className={`side-brand${collapsed ? " is-collapsed" : ""}`}>
            <img className="brand-mark" src="/brand.png" alt="Fab Bot" />
            {!collapsed && (
              <>
                <div className="brand-txt">
                  {/* 品牌只在这里出现一次：标题栏已改为应用菜单栏 */}
                  <div className="brand-name">Fab Bot</div>
                  <div className="brand-sub">半导体工厂 AI 助手</div>
                </div>
                <button type="button" className="brand-pill" title="服务状态"
                  data-menu-trigger="side" onClick={e => toggleBrand(e.currentTarget)}>
                  V{health?.version || "4.2"} <Icon name="chevron" size={12} />
                </button>
              </>
            )}
          </div>

          <div className="side-scroll">
            <nav className="nav-block">
              {NAV_MAIN.map(navBtn)}
            </nav>

            <div className="nav-group">
              {!collapsed && <div className="nav-group-title">运维管理</div>}
              {NAV_OPS.map(navBtn)}
            </div>

            {!collapsed && (
              <div className="nav-group">
                <div className="nav-group-title">最近会话 <span>({sessions.length})</span></div>
                {sessions.length === 0
                  ? <div className="nav-empty">暂无会话</div>
                  : sessions.slice(0, 4).map(s => (
                    <button key={s.id} type="button" className="nav-recent"
                      title={s.title} onClick={() => goSession(s.id)}>
                      <Icon name="clock" size={14} />
                      <span className="truncate">{s.title || "未命名会话"}</span>
                    </button>
                  ))}
              </div>
            )}
          </div>

          <div className="flex-1" />

          <div className={`side-user${collapsed ? " is-collapsed" : ""}`}>
            <span className="user-avatar">{(me.display_name || me.username).slice(0, 1)}</span>
            {!collapsed && (
              <>
                <div className="user-txt">
                  <div className="user-name">{me.display_name || me.username}</div>
                  <div className="user-role">{me.role}</div>
                </div>
                <button className="user-logout" title="退出登录" onClick={logout}>
                  <Icon name="logout" size={15} />
                </button>
              </>
            )}
          </div>

        </aside>

        {/* ── 内容区 ── */}
        <main className="flex-1 min-w-0 relative">
          <div key={view} className="view-enter">
            {view === "home" && <Home me={me} health={health} go={go} />}
            {view === "chat" && <Chat me={me} initialSession={openSession} />}
            {view === "kb" && <Knowledge me={me} />}
            {view === "data" && <Data me={me} />}
            {view === "tasks" && <Tasks me={me} />}
            {view === "settings" && <Settings me={me} health={health} dark={dark} setDark={setDark}
              glass={glass} setGlass={setGlass} refreshHealth={refreshHealth} />}
          </div>
        </main>
      </div>
    );
  }

  return (
    <>
      <TitleBar dark={dark} setDark={setDark} glass={glass} setGlass={setGlass}
        collapsed={collapsed} setCollapsed={setCollapsed} go={go}
        health={health} refreshHealth={refreshHealth} onLogout={logout} loggedIn={!!me}
        notif={<NotificationCenter go={go} enabled={!!me} />} />
      <div className="h-full">{body}</div>
      {/* 下拉渲染在侧栏之外：侧栏有 backdrop-filter + overflow:hidden，会裁剪 fixed 子元素 */}
      {brandOpen && me && <MenuPop items={brandItems} left={brandPos.left} top={brandPos.top}
        owner="side" minWidth={228} onClose={() => setBrandOpen(false)} />}
    </>
  );
}
