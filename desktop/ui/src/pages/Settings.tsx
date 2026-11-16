import React, { useState } from "react";
import { Me, Health, patchJSON } from "../api";
import { BigTitle, Card, SectionTitle, Switch, Segmented } from "../components/ui";

type GlassMode = "off" | "eco" | "on";

export default function Settings({ me, health, dark, setDark, glass, setGlass, refreshHealth, onLogoutAll }: {
  me: Me; health: Health | null; dark: boolean; setDark: (v: boolean) => void;
  glass: GlassMode; setGlass: (v: GlassMode) => void; refreshHealth: () => void;
  onLogoutAll: () => Promise<void>;
}) {
  const [oldPw, setOldPw] = useState(""); const [newPw, setNewPw] = useState("");
  const [msg, setMsg] = useState("");
  const [name, setName] = useState(me.display_name || "");

  const changePw = async () => {
    setMsg("");
    try { await patchJSON("/api/auth/me/password", { old_password: oldPw, new_password: newPw }); setMsg("✅ 密码已修改"); setOldPw(""); setNewPw(""); }
    catch (e: any) { setMsg("⚠️ " + e.message); }
  };
  const saveName = async () => {
    setMsg("");
    try { await patchJSON("/api/auth/me", { display_name: name }); setMsg("✅ 已保存"); }
    catch (e: any) { setMsg("⚠️ " + e.message); }
  };
  // C7: 全端登出 —— 吊销全部令牌, 由 App 清空登录态回到登录页
  const logoutAll = async () => {
    if (!confirm("确认全端登出？该账号在所有设备上的登录都将失效。")) return;
    setMsg("");
    try { await onLogoutAll(); }
    catch (e: any) { setMsg("⚠️ " + e.message); }
  };

  return (
    <div className="app-view"><div className="max-w-[720px]">
      <BigTitle sub="账号、外观与服务状态">设置</BigTitle>

      {/* B8: 云端 LLM 不可达自动降级提示 (区别于主动开启的 Mock 演示模式) */}
      {health?.llm.degraded && (
        <div className="ios-card p-3 mb-4 text-[12.5px] text-[#FF9500] bg-[#FF9500]/10 border-[#FF9500]/30">
          ⚠️ 云端模型不可达，已自动降级为 Mock 演示模式
        </div>
      )}

      <SectionTitle>外观</SectionTitle>
      <Card className="mb-4 flex items-center justify-between">
        <div><div className="font-semibold text-[14.5px]">深色模式</div>
          <div className="text-[12px] text-ios-label2">跟随切换，立即生效</div></div>
        <Switch checked={dark} onChange={setDark} />
      </Card>
      <Card className="mb-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div><div className="font-semibold text-[14.5px]">液态玻璃材质</div>
            <div className="text-[12px] text-ios-label2 mt-0.5">虹彩边缘、动态光斑与光照跟随；省电模式保留静态材质</div></div>
          <Segmented value={glass} onChange={setGlass} options={[
            { value: "off", label: "关闭" },
            { value: "eco", label: "省电" },
            { value: "on", label: "完整" },
          ]} />
        </div>
      </Card>

      <SectionTitle>账号</SectionTitle>
      <Card className="mb-4 space-y-3">
        <div className="flex items-center gap-3">
          <span className="text-[13px] text-ios-label2 w-[80px]">用户名</span>
          <span className="text-[14px] font-medium">{me.username} ({me.role})</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[13px] text-ios-label2 w-[80px]">显示名称</span>
          <input className="ios-input flex-1" value={name} onChange={e => setName(e.target.value)} />
          <button className="ios-btn-primary px-4 py-1.5 text-[13px]" onClick={saveName}>保存</button>
        </div>
        <div className="border-t border-black/5 dark:border-white/5 pt-3">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-[13px] text-ios-label2 w-[80px]">修改密码</span>
            <input className="ios-input flex-1" type="password" placeholder="当前密码" value={oldPw}
              onChange={e => setOldPw(e.target.value)} />
            <input className="ios-input flex-1" type="password" placeholder="新密码 (≥6位)" value={newPw}
              onChange={e => setNewPw(e.target.value)} />
            <button className="ios-btn-primary px-4 py-1.5 text-[13px]" disabled={!oldPw || newPw.length < 6}
              onClick={changePw}>修改</button>
          </div>
          {msg && <div className="text-[12.5px] px-1">{msg}</div>}
        </div>
        <div className="border-t border-black/5 dark:border-white/5 pt-3 flex items-center justify-between gap-3">
          <div className="text-[12px] text-ios-label2">丢失设备或怀疑令牌泄露时，吊销该账号所有设备的登录</div>
          <button className="ios-btn-ghost px-4 py-1.5 text-[13px] text-[#FF453A] shrink-0" onClick={logoutAll}>全端登出</button>
        </div>
      </Card>

      <SectionTitle>服务状态</SectionTitle>
      <Card className="mb-4 space-y-2 text-[13.5px]">
        <div className="flex justify-between"><span className="text-ios-label2">后端版本</span><span>{health?.version ?? "–"}</span></div>
        <div className="flex justify-between"><span className="text-ios-label2">模型服务</span>
          <span>{health ? (health.llm.mock ? `Mock 演示模式${health.llm.degraded ? "（自动降级）" : ""}` : health.llm.model) : "离线"}</span></div>
        <div className="flex justify-between"><span className="text-ios-label2">知识库</span>
          <span>{health ? `${health.kb_chunks} 片段` : "–"}</span></div>
        <div className="flex justify-between"><span className="text-ios-label2">Notes 接入</span>
          <span>{health?.notes_mode ?? "–"}</span></div>
        <div className="flex justify-between"><span className="text-ios-label2">我的权限</span><span>{me.role}</span></div>
      </Card>

      <div className="text-[11.5px] text-ios-label2 px-1 leading-5">
        数据安全：全部服务运行在工厂内网，生产数据经只读中间库接入，问答与查询全程留痕审计。
      </div>
    </div></div>
  );
}
