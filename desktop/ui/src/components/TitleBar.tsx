import React from "react";
import { Health } from "../api";
import { Icon, IconName } from "./icons";
import { MenuItem, MenuPop, useMenuDismiss } from "./Menu";
import { Modal } from "./ui";

/**
 * 无边框窗口的「应用菜单栏」+ 缩放热区。
 *
 * WebView2 是独立 HWND，WPF 控件和 WindowChrome 的原生缩放边框都无法叠在网页上
 * （airspace），所以窗口按钮 / 拖拽 / 缩放都放在网页里，用 WebMessage 交给 C# 执行。
 * 品牌信息只在侧栏出现一次，这里改为桌面客户端惯用的菜单栏。
 */
const DESKTOP =
  typeof window !== "undefined" &&
  (!!(window as any).chrome?.webview?.postMessage ||
    new URLSearchParams(window.location.search).has("desktop"));

/* 右上角留给 — ▢ ✕ 按钮，不做角缩放热区，避免遮挡点击 */
const EDGES = ["top", "right", "bottom", "left", "tl", "bl", "br"];

function send(action: string) {
  const wv = (window as any).chrome?.webview;
  if (wv?.postMessage) wv.postMessage(action);
}

export type GlassMode = "off" | "eco" | "on";

type Props = {
  dark: boolean; setDark: (v: boolean) => void;
  glass: GlassMode; setGlass: (v: GlassMode) => void;
  collapsed: boolean; setCollapsed: (v: boolean) => void;
  go: (v: string) => void;
  health: Health | null;
  refreshHealth: () => void;
  onLogout: () => void;
  loggedIn: boolean;
};

type MenuId = "file" | "edit" | "view" | "window" | "help" | "quick";

const MENU_LABELS: { id: MenuId; label: string; key: string }[] = [
  { id: "file", label: "文件", key: "F" },
  { id: "edit", label: "编辑", key: "E" },
  { id: "view", label: "视图", key: "V" },
  { id: "window", label: "窗口", key: "W" },
  { id: "help", label: "帮助", key: "H" },
];

export default function TitleBar(p: Props) {
  const dragging = React.useRef(false);
  const resizing = React.useRef<string | null>(null);
  const [open, setOpen] = React.useState<MenuId | null>(null);
  const [pos, setPos] = React.useState({ left: 0 });
  const [about, setAbout] = React.useState(false);
  const [shortcuts, setShortcuts] = React.useState(false);

  useMenuDismiss(open !== null, () => setOpen(null), "title");

  React.useEffect(() => {
    if (!DESKTOP) return;
    send("hello");                       // 握手：确认网页 → C# 的消息通道已建立
    const move = (e: PointerEvent) => {
      if (dragging.current) send(`dragMove:${e.screenX},${e.screenY}`);
      else if (resizing.current) send(`resizeMove:${e.screenX},${e.screenY}`);
    };
    const up = () => {
      if (dragging.current) { dragging.current = false; send("dragEnd"); }
      if (resizing.current) { resizing.current = null; send("resizeEnd"); }
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    window.addEventListener("blur", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      window.removeEventListener("blur", up);
    };
  }, []);

  const reload = () => DESKTOP ? send("reload") : window.location.reload();
  const external = (path: string) => {
    const url = window.location.origin + path;
    if (DESKTOP) send("openexternal:" + url);
    else window.open(url, "_blank");
  };
  const docCmd = (cmd: string) => {
    try { document.execCommand(cmd); } catch { /* 网页预览下可能不支持 */ }
  };

  // 菜单里标注的快捷键要真的可用：WebView2 禁用了浏览器默认加速键，这里自行接管
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.ctrlKey || e.altKey || e.shiftKey) return;
      const k = e.key.toLowerCase();
      if (k === "n") { e.preventDefault(); p.go("chat"); }
      else if (k === "r") { e.preventDefault(); reload(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const menus: Record<MenuId, MenuItem[]> = {
    file: [
      { label: "新建对话", icon: "plus", hint: "Ctrl+N", onSelect: () => p.go("chat") },
      { label: "打开知识库", icon: "book", onSelect: () => p.go("kb") },
      { label: "打开数据台", icon: "database", onSelect: () => p.go("data") },
      { label: "刷新界面", icon: "refresh", hint: "Ctrl+R", separator: true, onSelect: reload },
      { label: "退出登录", icon: "logout", disabled: !p.loggedIn, onSelect: p.onLogout },
      { label: "完全退出程序", icon: "power", danger: true, disabled: !DESKTOP,
        separator: true, onSelect: () => send("exit") },
    ],
    edit: [
      { label: "复制所选内容", icon: "file", hint: "Ctrl+C", onSelect: () => docCmd("copy") },
      { label: "全选", icon: "check", hint: "Ctrl+A", onSelect: () => docCmd("selectAll") },
      { label: "清除选择", icon: "panel", separator: true, onSelect: () => window.getSelection()?.removeAllRanges() },
    ],
    view: [
      { label: "深色模式", icon: p.dark ? "moon" : "sun", checked: p.dark, onSelect: () => p.setDark(!p.dark) },
      { label: "液态玻璃 · 关闭", checked: p.glass === "off", separator: true, onSelect: () => p.setGlass("off") },
      { label: "液态玻璃 · 省电", checked: p.glass === "eco", onSelect: () => p.setGlass("eco") },
      { label: "液态玻璃 · 完整", checked: p.glass === "on", onSelect: () => p.setGlass("on") },
      { label: p.collapsed ? "展开侧边栏" : "折叠侧边栏", icon: "panel", separator: true,
        onSelect: () => p.setCollapsed(!p.collapsed) },
    ],
    window: [
      { label: "最小化", icon: "window", disabled: !DESKTOP, onSelect: () => send("minimize") },
      { label: "最大化 / 还原", icon: "window", disabled: !DESKTOP, onSelect: () => send("maximize") },
      { label: "收起到托盘", icon: "panel", disabled: !DESKTOP, onSelect: () => send("close") },
      { label: "完全退出程序", icon: "power", danger: true, disabled: !DESKTOP, separator: true, onSelect: () => send("exit") },
    ],
    help: [
      { label: "快捷键", icon: "keyboard", onSelect: () => setShortcuts(true) },
      { label: "接口文档（浏览器）", icon: "external", onSelect: () => external("/docs") },
      { label: "管理后台（浏览器）", icon: "external", onSelect: () => external("/admin") },
      { label: "检查服务状态", icon: "refresh", separator: true, onSelect: p.refreshHealth },
      { label: "关于 Fab Bot", icon: "info", onSelect: () => setAbout(true) },
    ],
    quick: [
      { label: "深色模式", icon: p.dark ? "moon" : "sun", checked: p.dark, onSelect: () => p.setDark(!p.dark) },
      { label: "液态玻璃 · 关闭", checked: p.glass === "off", separator: true, onSelect: () => p.setGlass("off") },
      { label: "液态玻璃 · 省电", checked: p.glass === "eco", onSelect: () => p.setGlass("eco") },
      { label: "液态玻璃 · 完整", checked: p.glass === "on", onSelect: () => p.setGlass("on") },
      { label: "设置…", icon: "settings", separator: true, onSelect: () => p.go("settings") },
    ],
  };

  const toggleMenu = (id: MenuId, el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    setPos({ left: Math.max(4, r.left - 4) });
    setOpen(cur => cur === id ? null : id);
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (!DESKTOP || e.button !== 0) return;
    if ((e.target as HTMLElement | null)?.closest?.("button")) return;
    dragging.current = true;
    send(`dragStart:${e.screenX},${e.screenY}`);
  };
  const onDouble = (e: React.MouseEvent) => {
    if (!DESKTOP) return;
    if ((e.target as HTMLElement | null)?.closest?.("button")) return;
    send("maximize");
  };
  const onResizeDown = (e: React.PointerEvent, edge: string) => {
    if (!DESKTOP || e.button !== 0) return;
    e.stopPropagation();
    resizing.current = edge;
    send(`resizeStart:${edge}:${e.screenX},${e.screenY}`);
  };

  const iconBtn = (name: IconName, title: string, onClick?: () => void, trigger?: MenuId) => (
    <button type="button" className="tb-icon" title={title}
      data-menu-trigger={trigger ? "title" : undefined}
      onClick={e => trigger ? toggleMenu(trigger, e.currentTarget) : onClick?.()}>
      <Icon name={name} size={16} />
    </button>
  );

  return (
    <>
      <div className="titlebar" onPointerDown={onPointerDown} onDoubleClick={onDouble}>
        <div className="tb-tools">
          {iconBtn("panel", "折叠 / 展开侧边栏", () => p.setCollapsed(!p.collapsed))}
          {iconBtn("search", "新建对话", () => p.go("chat"))}
          {iconBtn("sliders", "快速设置", undefined, "quick")}
        </div>
        <span className="tb-tools-sep" aria-hidden />

        <div className="tb-menus">
          {MENU_LABELS.map(m => (
            <button key={m.id} type="button" data-menu-trigger="title"
              className={`tb-menu-btn${open === m.id ? " is-open" : ""}`}
              onClick={e => toggleMenu(m.id, e.currentTarget)}
              onPointerEnter={e => { if (open && open !== m.id) toggleMenu(m.id, e.currentTarget); }}>
              {m.label}({m.key})
            </button>
          ))}
          <button type="button" className="tb-menu-btn" onClick={() => setAbout(true)}>关于(A)</button>
        </div>

        <div className="tb-right">
          <button className="tb-action" title="刷新界面" onClick={reload}>
            <Icon name="refresh" size={15} />
          </button>
          {DESKTOP ? (
            <>
              <span className="tb-divider" />
              <button className="tb-win" title="最小化" onClick={() => send("minimize")}>—</button>
              <button className="tb-win" title="最大化 / 还原" onClick={() => send("maximize")}>▢</button>
              <button className="tb-win tb-win-close" title="关闭到托盘（托盘右键可退出）"
                onClick={() => send("close")}>✕</button>
            </>
          ) : (
            <span className="tb-badge" title="窗口按钮与拖拽仅在桌面版可用">网页预览 · 窗口控件请用 FabBot.exe</span>
          )}
        </div>
      </div>

      {open && <MenuPop items={menus[open]} left={pos.left} top="var(--tb-h)" owner="title"
        minWidth={open === "file" || open === "help" ? 236 : 214}
        onClose={() => setOpen(null)} />}

      {DESKTOP && (
        <div className="resize-layer">
          {EDGES.map(edge => (
            <div key={edge} className={`rs rs-${edge}`}
              onPointerDown={e => onResizeDown(e, edge)} />
          ))}
        </div>
      )}

      {about && (
        <Modal title="关于 Fab Bot" readable onClose={() => setAbout(false)}>
          <img className="about-mark" src="/brand.png" alt="Fab Bot" />
          <div className="about-name">Fab Bot</div>
          <div className="about-sub">半导体工厂 AI 助手 · 内网桌面版</div>
          <div className="about-rows">
            <div><span>版本</span><b>V{p.health?.version || "4.2"}</b></div>
            <div><span>服务状态</span><b>{p.health?.status === "ok" ? "运行正常" : "未连接"}</b></div>
            <div><span>推理模型</span><b>{p.health ? (p.health.llm.mock ? "Mock 演示" : p.health.llm.model) : "–"}</b></div>
            <div><span>知识库</span><b>{p.health ? `${p.health.kb_chunks} 片段` : "–"}</b></div>
          </div>
          <button className="ios-btn-ghost w-full mt-4" onClick={() => { setAbout(false); p.refreshHealth(); }}>
            刷新状态
          </button>
        </Modal>
      )}

      {shortcuts && (
        <Modal title="快捷键" readable onClose={() => setShortcuts(false)}>
          <div className="about-rows">
            <div><span>唤起 / 隐藏窗口</span><b>Ctrl + Alt + F</b></div>
            <div><span>新建对话</span><b>Ctrl + N</b></div>
            <div><span>刷新界面</span><b>Ctrl + R</b></div>
            <div><span>关闭菜单 / 弹层</span><b>Esc</b></div>
            <div><span>标题栏双击</span><b>最大化 / 还原</b></div>
          </div>
        </Modal>
      )}
    </>
  );
}
