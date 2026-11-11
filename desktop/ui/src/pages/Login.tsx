import React, { useState } from "react";
import { Me, postJSON } from "../api";

export default function Login({ onLogin }: { onLogin: (u: Me) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const r = await postJSON<{ user: Me }>("/api/auth/login",
        { username: username.trim(), password });
      onLogin(r.user);
    } catch (ex: any) {
      setErr(ex.message || "登录失败");
    } finally { setBusy(false); }
  };

  return (
    <div className="h-full grid place-items-center bg-ios-bg dark:bg-black">
      <form onSubmit={submit}
        className="w-[360px] bg-white/80 dark:bg-[#1C1C1E]/90 backdrop-blur-2xl rounded-[20px] shadow-float p-8">
        <div className="text-center mb-6">
          <div className="text-[40px] leading-none mb-2">⚙️</div>
          <div className="text-[20px] font-bold">Fab Bot</div>
          <div className="text-[12.5px] text-ios-label2 mt-1">半导体工厂智能助手 · 登录</div>
        </div>
        <div className="text-[12px] text-[#FF453A] min-h-[18px] mb-1">{err}</div>
        <input className="ios-input mb-3" placeholder="用户名" value={username}
          onChange={e => setUsername(e.target.value)} autoFocus />
        <input className="ios-input mb-4" type="password" placeholder="密码" value={password}
          onChange={e => setPassword(e.target.value)} />
        <button className="ios-btn-primary w-full py-2.5 text-[15px]" disabled={busy || !username || !password}>
          {busy ? "登录中…" : "登 录"}
        </button>
        <div className="text-[11px] text-ios-label2 mt-4 text-center leading-5">
          首次部署默认账号 admin / admin123<br />登录后请立即在设置中修改密码
        </div>
      </form>
    </div>
  );
}
