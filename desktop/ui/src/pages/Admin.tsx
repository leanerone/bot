import React, { useEffect, useState } from "react";
import { BigTitle, Modal, Switch } from "../components/ui";
import { getJSON, patchJSON, postJSON, putJSON, delJSON } from "../api";

/* B1: 桌面管理页 —— 统计 / 用户 / 审计 / 会话 / 配置+推送测试 (仅 admin 角色可见入口) */

const TABS = ["统计", "用户", "审计", "会话", "配置"] as const;
type Tab = typeof TABS[number];

export default function Admin({ me }: { me: { id: string; role: string; username: string } }) {
  const [tab, setTab] = useState<Tab>("统计");
  if (me.role !== "admin") return <div className="p-6 text-ios-label2">需要管理员权限</div>;
  return (
    <div className="p-6">
      <BigTitle sub="系统统计 · 用户 · 审计 · 会话 · 配置与推送">管理</BigTitle>
      <div className="flex gap-1.5 mb-4">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-full text-[13px] transition-colors
              ${tab === t ? "bg-[#0A84FF] text-white font-semibold" : "ios-btn-ghost"}`}>{t}</button>
        ))}
      </div>
      {tab === "统计" && <StatsTab goNotify={t => setTab(t as Tab)} />}
      {tab === "用户" && <UsersTab meId={me.id} />}
      {tab === "审计" && <AuditTab />}
      {tab === "会话" && <SessionsTab />}
      {tab === "配置" && <ConfigTab />}
    </div>
  );
}

/* ── 统计 + 推送测试 ── */

function StatsTab({ goNotify }: { goNotify: (t: string) => void }) {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => { getJSON<any>("/api/admin/stats").then(setStats).catch(() => {}); }, []);
  if (!stats) return <div className="skeleton-shimmer ios-card h-24" />;
  const cards: [string, any][] = [
    ["用户", stats.users], ["会话", stats.sessions], ["消息", stats.messages],
    ["好评", stats.feedback_up], ["差评", stats.feedback_down],
    ["审计条目", stats.audit_count ?? "–"],
  ];
  return (
    <div>
      <div className="grid grid-cols-3 gap-3">
        {cards.map(([k, v]) => (
          <div key={k} className="ios-card p-4">
            <div className="text-[26px] font-bold">{v ?? "–"}</div>
            <div className="text-[12.5px] text-ios-label2">{k}</div>
          </div>
        ))}
      </div>
      <NotifyTestCard />
    </div>
  );
}

/* B3: 推送测试卡 (Teams 为默认渠道) */
function NotifyTestCard() {
  const [platform, setPlatform] = useState("teams");
  const [msg, setMsg] = useState("Fab Bot 推送测试 (来自管理页)");
  const [result, setResult] = useState("");
  const send = async () => {
    try {
      await postJSON("/api/admin/notify/test", { platform, text: msg });
      setResult("✅ 已发送 (若未收到请检查 webhook 配置)");
    } catch (e: any) { setResult("❌ " + e.message); }
  };
  return (
    <div className="ios-card p-4 mt-4">
      <div className="font-semibold text-[14px] mb-2">推送测试</div>
      <div className="flex gap-2 items-center flex-wrap">
        <select value={platform} onChange={e => setPlatform(e.target.value)}
          className="ios-input !py-1.5 text-[13px] w-auto">
          {["teams", "wechat", "dingtalk", "feishu"].map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <input className="ios-input flex-1 min-w-[200px] text-[13px]" value={msg}
          onChange={e => setMsg(e.target.value)} />
        <button className="ios-btn-primary px-4 py-1.5 text-[13px]" onClick={send}>发送</button>
      </div>
      {result && <div className="text-[12.5px] mt-2 text-ios-label2">{result}</div>}
      <div className="text-[11.5px] text-ios-label2 mt-2">
        Teams 双格式: notify.teams_format = connector | flow (Power Automate); webhook 配置在 config.yaml
      </div>
    </div>
  );
}

/* ── 用户管理 ── */

function UsersTab({ meId }: { meId: string }) {
  const [users, setUsers] = useState<any[]>([]);
  const [addOpen, setAddOpen] = useState(false);
  const load = () => getJSON<any>("/api/admin/users").then(r => setUsers(r.users)).catch(() => {});
  useEffect(() => { load(); }, []);
  const patch = async (id: string, body: any) => {
    try { await patchJSON(`/api/admin/users/${id}`, body); load(); }
    catch (e: any) { alert(e.message); }
  };
  const resetPw = async (id: string) => {
    const pw = prompt("新密码 (≥6 位):");
    if (!pw) return;
    try { await patchJSON(`/api/admin/users/${id}/password`, { password: pw }); alert("✅ 已重置"); }
    catch (e: any) { alert(e.message); }
  };
  const create = async (body: any) => {
    try { await postJSON("/api/admin/users", body); setAddOpen(false); load(); }
    catch (e: any) { alert(e.message); }
  };
  return (
    <div>
      <button className="ios-btn-primary mb-3 px-4 py-1.5 text-[13px]" onClick={() => setAddOpen(true)}>＋ 新建用户</button>
      <div className="ios-card overflow-hidden">
        <table className="w-full text-[13px]">
          <thead><tr className="bg-black/[.03] dark:bg-white/[.05] text-ios-label2">
            {["账号", "显示名", "角色", "状态", ""].map(h => <th key={h} className="text-left px-3 py-2 font-semibold">{h}</th>)}
          </tr></thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t border-black/5 dark:border-white/5">
                <td className="px-3 py-2 font-medium">{u.username}</td>
                <td className="px-3 py-2">{u.display_name}</td>
                <td className="px-3 py-2">
                  <select value={u.role} disabled={u.id === meId}
                    onChange={e => patch(u.id, { role: e.target.value })}
                    className="ios-input !py-0.5 text-[12px] w-auto">
                    {["viewer", "user", "admin"].map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td className="px-3 py-2">
                  {u.id === meId ? <span className="text-ios-label2">当前账号</span> : (
                    <span className={`px-2 py-0.5 rounded-full text-[11px]
                      ${u.disabled ? "bg-[#FF453A]/15 text-[#FF453A]" : "bg-[#30D158]/15 text-[#30D158]"}`}>
                      {u.disabled ? "已禁用" : "正常"}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-right space-x-2 text-[12px]">
                  <button className="ios-btn-ghost px-2 py-0.5" onClick={() => resetPw(u.id)}>重置密码</button>
                  {u.id !== meId && (
                    <button className="ios-btn-ghost px-2 py-0.5"
                      onClick={() => patch(u.id, { disabled: !u.disabled })}>
                      {u.disabled ? "启用" : "禁用"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {addOpen && <AddUserModal onClose={() => setAddOpen(false)} onCreate={create} />}
    </div>
  );
}

function AddUserModal({ onClose, onCreate }: { onClose: () => void; onCreate: (b: any) => void }) {
  const [f, setF] = useState({ username: "", password: "", role: "user", display_name: "" });
  return (
    <Modal title="新建用户" onClose={onClose}>
      <div className="space-y-2.5">
        {(["username", "display_name", "password"] as const).map(k => (
          <input key={k} className="ios-input w-full" placeholder={{ username: "账号", display_name: "显示名", password: "密码 (≥6位)" }[k]}
            type={k === "password" ? "password" : "text"} value={f[k]}
            onChange={e => setF({ ...f, [k]: e.target.value })} />
        ))}
        <select className="ios-input w-full" value={f.role}
          onChange={e => setF({ ...f, role: e.target.value })}>
          {["viewer", "user", "admin"].map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <button className="ios-btn-primary w-full py-2" onClick={() => onCreate(f)}>创建</button>
      </div>
    </Modal>
  );
}

/* ── 审计 ── */

function AuditTab() {
  const [rows, setRows] = useState<any[]>([]);
  const [qUser, setQUser] = useState("");
  const load = (user = "") => {
    const qs = user ? `?user=${encodeURIComponent(user)}&limit=300` : "?limit=300";
    getJSON<any>(`/api/admin/audit${qs}`).then(r => setRows(r.audit)).catch(() => {});
  };
  useEffect(() => { load(); }, []);
  return (
    <div>
      <div className="flex gap-2 mb-3">
        <input className="ios-input flex-1 text-[13px]" placeholder="按用户名过滤…"
          value={qUser} onChange={e => setQUser(e.target.value)} />
        <button className="ios-btn-primary px-4 py-1.5 text-[13px]" onClick={() => load(qUser)}>查询</button>
        <a className="ios-btn-ghost px-4 py-1.5 text-[13px] no-underline" href="/api/admin/audit/export?limit=1000">导出 CSV</a>
      </div>
      <div className="ios-card overflow-x-auto max-h-[480px] overflow-y-auto">
        <table className="w-full text-[12px]">
          <thead><tr className="bg-black/[.03] dark:bg-white/[.05] text-ios-label2 sticky top-0">
            {["时间", "用户", "API", "意图", "状态", "内容"].map(h => <th key={h} className="text-left px-2.5 py-1.5 font-semibold">{h}</th>)}
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-black/5 dark:border-white/5">
                <td className="px-2.5 py-1 whitespace-nowrap">{(r.ts || "").slice(5, 19)}</td>
                <td className="px-2.5 py-1">{r.user}</td>
                <td className="px-2.5 py-1">{r.api}</td>
                <td className="px-2.5 py-1">{r.intent || "–"}</td>
                <td className={`px-2.5 py-1 ${r.status && r.status !== "ok" ? "text-[#FF453A]" : ""}`}>{r.status}</td>
                <td className="px-2.5 py-1 max-w-[280px] truncate" title={r.question}>{r.question}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── 全用户会话管理 ── */

function SessionsTab() {
  const [rows, setRows] = useState<any[]>([]);
  const load = () => getJSON<any>("/api/admin/sessions").then(r => setRows(r.sessions)).catch(() => {});
  useEffect(() => { load(); }, []);
  const del = async (id: string) => {
    if (!confirm("确认删除该会话 (所有用户视角)?")) return;
    await delJSON(`/api/admin/sessions/${id}`);
    load();
  };
  return (
    <div className="ios-card overflow-hidden">
      <table className="w-full text-[13px]">
        <thead><tr className="bg-black/[.03] dark:bg-white/[.05] text-ios-label2">
          {["用户", "标题", "消息数", "更新时间", ""].map(h => <th key={h} className="text-left px-3 py-2 font-semibold">{h}</th>)}
        </tr></thead>
        <tbody>
          {rows.map(s => (
            <tr key={s.id} className="border-t border-black/5 dark:border-white/5">
              <td className="px-3 py-2">{s.username || s.user_id}</td>
              <td className="px-3 py-2">{s.title}</td>
              <td className="px-3 py-2">{s.message_count}</td>
              <td className="px-3 py-2 text-ios-label2">{(s.updated_at || "").slice(0, 19)}</td>
              <td className="px-3 py-2 text-right">
                <button className="text-[#FF453A] text-[12px]" onClick={() => del(s.id)}>删除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── B2: 配置管理 (白名单键读写) ── */

function ConfigTab() {
  const [cfgData, setCfgData] = useState<Record<string, any>>({});
  const [draft, setDraft] = useState<Record<string, any>>({});
  const [msg, setMsg] = useState("");
  useEffect(() => {
    getJSON<any>("/api/admin/config").then(r => { setCfgData(r.config || {}); setDraft(r.config || {}); }).catch(() => {});
  }, []);
  const save = async () => {
    try {
      // A1: 后端为 PUT + 扁平 key→value (draft 本身即扁平点路径键); 被拒键走 400 detail
      const r = await putJSON<any>("/api/admin/config", draft);
      const rejected: string[] = r.rejected || [];
      setMsg(rejected.length
        ? `⚠️ 已应用 ${r.applied?.length ?? 0} 项, 被拒绝: ${rejected.join(", ")}`
        : `✅ 已保存 ${r.applied?.length ?? 0} 项 (${r.restart_hint || "重启后生效"})`);
    } catch (e: any) { setMsg("❌ " + e.message); }
  };
  const entries = Object.entries(cfgData);
  return (
    <div>
      <div className="ios-card p-4">
        <div className="font-semibold text-[14px] mb-1">系统配置 (白名单键)</div>
        <div className="text-[11.5px] text-ios-label2 mb-3">
          密码/api_key 类键永不出现在此处; 修改写入 config.yaml (自动备份)
        </div>
        <div className="space-y-2.5">
          {entries.map(([k, v]) => (
            <label key={k} className="flex items-center gap-3">
              <span className="text-[13px] font-mono w-[240px] shrink-0">{k}</span>
              {typeof v === "boolean" ? (
                <Switch checked={!!draft[k]} onChange={nv => setDraft({ ...draft, [k]: nv })} />
              ) : (
                <input className="ios-input flex-1 text-[13px]" value={draft[k] ?? ""}
                  onChange={e => setDraft({ ...draft, [k]: e.target.value })} />
              )}
            </label>
          ))}
          {!entries.length && <div className="text-ios-label2 text-[13px]">暂无可编辑键 (后端白名单为空)</div>}
        </div>
        {entries.length > 0 && (
          <button className="ios-btn-primary mt-4 px-5 py-1.5 text-[13px]" onClick={save}>保存配置</button>
        )}
        {msg && <div className="text-[12.5px] mt-2">{msg}</div>}
      </div>
    </div>
  );
}
