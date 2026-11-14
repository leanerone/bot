import React, { useEffect, useState } from "react";
import { BigTitle, Modal } from "../components/ui";
import { getJSON, postJSON } from "../api";

/* D5: 技能中心 —— SKILL.md 声明的能力卡片 + 受控执行 + 执行结果 */

interface Skill {
  name: string; version: string; runtime: string; server?: string;
  tools?: string[]; permissions?: string[]; description?: string;
  path?: string; body?: string;
}

export default function Skills({ me }: { me: { role: string; username: string } }) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [detail, setDetail] = useState<Skill | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [result, setResult] = useState<{ name: string; ok: boolean; text: string } | null>(null);
  const [args, setArgs] = useState<Record<string, string>>({});

  const load = () =>
    getJSON<{ skills: Skill[]; errors: string[] }>("/api/skills")
      .then(r => { setSkills(r.skills); setErrors(r.errors); }).catch(() => {});
  useEffect(() => { load(); }, []);

  const run = async (s: Skill) => {
    setRunning(s.name);
    try {
      const r = await postJSON<any>(`/api/skills/${s.name}/run`, { args: args[s.name] ? { query: args[s.name] } : {} });
      setResult({ name: s.name, ok: !!r.ok, text: JSON.stringify(r.ok ? r.data : r.error, null, 2) });
    } catch (e: any) {
      setResult({ name: s.name, ok: false, text: e.message });
    } finally {
      setRunning(null);
    }
  };

  const permBadge = (p: string) => {
    const write = /write|delete|update|send/i.test(p);
    return (
      <span key={p} className={`text-[10.5px] px-1.5 py-0.5 rounded-full
        ${write ? "bg-[#FF453A]/15 text-[#FF453A]" : "bg-[#30D158]/15 text-[#30D158]"}`}>{p}</span>
    );
  };

  return (
    <div className="p-6">
      <BigTitle sub="SKILL.md 声明能力 · 宿主注入环境 · 受控执行 (写入权限需确认卡)">技能中心</BigTitle>
      {!!errors.length && (
        <div className="ios-card p-3 mb-3 text-[12.5px] text-[#FF9500]">
          定义校验告警: {errors.join("; ")}
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        {skills.map(s => (
          <div key={s.name} className="ios-card p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-semibold text-[15px]">{s.name} <span className="text-ios-label2 text-[12px]">v{s.version}</span></div>
                <div className="text-[12.5px] text-ios-label2 mt-0.5">{s.description || ""}</div>
              </div>
              <span className="text-[10.5px] px-1.5 py-0.5 rounded-full bg-[#0A84FF]/15 text-[#0A84FF] shrink-0">
                {s.runtime}
              </span>
            </div>
            <div className="flex flex-wrap gap-1 mt-2">
              {(s.permissions || []).map(permBadge)}
              {(s.tools || []).map(t => (
                <span key={t} className="text-[10.5px] px-1.5 py-0.5 rounded-full bg-black/[.05] dark:bg-white/[.08] font-mono">{t}</span>
              ))}
            </div>
            <div className="flex items-center gap-2 mt-3">
              <input className="ios-input flex-1 text-[12.5px]" placeholder="执行参数 (query/question, 可留空)"
                value={args[s.name] || ""}
                onChange={e => setArgs({ ...args, [s.name]: e.target.value })} />
              <button className="ios-btn-primary px-3 py-1.5 text-[12.5px]" disabled={running === s.name}
                onClick={() => run(s)}>
                {running === s.name ? "执行中…" : "▶ 执行"}
              </button>
              <button className="ios-btn-ghost px-2.5 py-1.5 text-[12.5px]"
                onClick={() => setDetail(s)}>详情</button>
            </div>
          </div>
        ))}
        {!skills.length && <div className="text-ios-label2 text-[13px]">未发现技能 (skills/ 目录为空)</div>}
      </div>

      {detail && (
        <Modal title={`${detail.name} · v${detail.version}`} onClose={() => setDetail(null)} wide>
          <div className="text-[12.5px] leading-6 whitespace-pre-wrap font-mono selectable">
            {detail.body || "(无说明)"}
          </div>
        </Modal>
      )}
      {result && (
        <Modal title={`执行结果 · ${result.name}`} onClose={() => setResult(null)} wide>
          <div className={`text-[12.5px] mb-2 ${result.ok ? "text-[#30D158]" : "text-[#FF453A]"}`}>
            {result.ok ? "✅ 执行成功 (已写入审计)" : "❌ 执行失败"}
          </div>
          <pre className="whitespace-pre-wrap text-[12px] leading-5 bg-black/[.03] dark:bg-white/[.05] rounded-[10px] p-3.5 max-h-[320px] overflow-auto">{result.text}</pre>
        </Modal>
      )}
    </div>
  );
}
