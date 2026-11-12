import React from "react";
import { Icon, IconName } from "./icons";

/** 应用菜单栏 / 侧栏品牌区共用的下拉面板 */
export type MenuItem = {
  label: string;
  icon?: IconName;
  hint?: string;
  checked?: boolean;
  disabled?: boolean;
  danger?: boolean;
  separator?: boolean;         // 在这一项上方插入分隔线
  onSelect?: () => void;
};

export function MenuPop({ items, onClose, left, top, minWidth = 214, owner = "menu" }: {
  items: MenuItem[]; onClose: () => void; left: number; top: string | number;
  minWidth?: number; owner?: string;
}) {
  return (
    <div className="menu-pop glass" data-owner={owner} style={{ left, top, minWidth }}
      onPointerDown={e => e.stopPropagation()} onClick={e => e.stopPropagation()}>
      {items.map((it, i) => (
        <React.Fragment key={it.label + i}>
          {it.separator && <div className="menu-sep" />}
          <button type="button" className={`menu-item${it.danger ? " is-danger" : ""}`}
            disabled={it.disabled} onClick={() => { it.onSelect?.(); onClose(); }}>
            <span className="menu-ic">
              {it.checked ? <Icon name="check" size={14} />
                : it.icon ? <Icon name={it.icon} size={15} /> : null}
            </span>
            <span className="menu-label">{it.label}</span>
            {it.hint && <span className="menu-hint">{it.hint}</span>}
          </button>
        </React.Fragment>
      ))}
    </div>
  );
}

/** 点击面板 / 触发器以外的地方、或按 Esc 时关闭菜单；owner 用于隔离多个菜单 */
export function useMenuDismiss(open: boolean, close: () => void, owner: string) {
  const cb = React.useRef(close);
  cb.current = close;
  const own = React.useRef(owner);
  own.current = owner;
  React.useEffect(() => {
    if (!open) return;
    const down = (e: PointerEvent) => {
      const t = e.target as HTMLElement | null;
      if (t?.closest?.(`.menu-pop[data-owner="${own.current}"]`) ||
          t?.closest?.(`[data-menu-trigger="${own.current}"]`)) return;
      cb.current();
    };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") cb.current(); };
    document.addEventListener("pointerdown", down, true);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", down, true);
      document.removeEventListener("keydown", key);
    };
  }, [open]);
}
