import React, { useEffect, useState } from "react";
import { BigTitle, Modal } from "../components/ui";
import { getJSON, postJSON } from "../api";
import { mdToHtml } from "../lib/md";

/* D5: 技能中心 —— SKILL.md 声明的能力卡片 + 受控执行 + 执行结果
   C10: viewer 只读 (执行置灰) + 详情 Markdown 渲染 + 最近执行审计 */

interface Skill {
  name: string; version: string; runtime: string; server?: string;
  tools?: string[]; permissions?: string[]; description?: string;
  path?: string; body?: string;
}
interface SkillRun { ts: string; status: string; ms: number; args: Record<string, any> }

/* A3: text2sql 技能映射宿主 sql_query 工具, 参数键为 question; 其余为 query */
const argKeyFor = (s: Skill) =>
  (s.tools || []).some(t => t === "text2sql_query" || t === "sql_query") ? "question" : "query";

export default function Skills({ me }: { me: { role: string; username: string } }) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [detail, setDetail] = useState<Skill | null>(null);
  const [runs, setRuns] = useState<SkillRun[] | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [result, setResult] = useState<{ name: string; ok: boolean; text: string } | null>(null);
  const [confirm, setConfirm] = useState<{ skill: Skill; error: string } | null>(null);
  const [args, setArgs] = useState<Record<string, string>>({});

  const canRun = me.role !== "viewer";   // C10: 执行需 user+ 权限

  const load = () =>
    getJSON<{ skills: Skill[]; errors: string[] }>("/api/skills")
      .then(r => { setSkills(r.skills); setErrors(r.errors); }).catch(() => {});
  useEffect(() => { load(); }, []);

  const run = async (s: Skill, confirmed = false) => {
    setRunning(s.name);
    try {
      const input = args[s.name];
      const runArgs: Record<string, any> = input ? { [argKeyFor(s)]: input } : {};
      if (confirmed) runArgs._confirmed = true;   // C8: 写操作确认卡通过后携带
      const r = await postJSON<any>(`/api/skills/${s.name}/run`, { args: runArgs });
      if (r.confirm_required === true) {
        setConfirm({ skill: s, error: r.error || "该技能包含写操作, 需要确认后执行" });
      } else {
        setResult({ name: s.name, ok: !!r.ok, text: JSON.stringify(r.ok ? r.data : r.error, null, 2) });
      }
    } catch (e: any) {
      setResult({ name: s.name, ok: false, text: e.message });
    } finally {
      setRunning(null);
    }
  };

  /* C2: 单技能详情走 /api/skills/{name} (旧单段通配路由已废弃); 失败时回退列表数据 */
  const openDetail = (s: Skill) => {
    setDetail(s);
    setRuns(null);
    getJSON<{ skill: Skill }>(`/api/skills/${s.name}`)
      .then(r => { if (r.skill) setDetail(d => (d?.name === s.name ? r.skill : d)); })
      .catch(() => {});
    getJSON<{ runs: SkillRun[] }>(`/api/skills/${s.name}/runs`)
      .then(r => setRuns(r.runs || []))
      .catch(() => setRuns([]));
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
              <input className="ios-input flex-1 text-[12.5px]" placeholder={`执行参数 (${argKeyFor(s)}, 可留空)`}
                value={args[s.name] || ""}
                onChange={e => setArgs({ ...args, [s.name]: e.target.value })} />
              <button className={`ios-btn-primary px-3 py-1.5 text-[12.5px] ${canRun ? "" : "opacity-40 cursor-not-allowed"}`}
                disabled={running === s.name || !canRun}
                title={canRun ? undefined : "当前角色为 viewer (只读), 执行技能需要 user 及以上权限"}
                onClick={() => run(s)}>
                {running === s.name ? "执行中…" : "▶ 执行"}
              </button>
              <button className="ios-btn-ghost px-2.5 py-1.5 text-[12.5px]"
                onClick={() => openDetail(s)}>详情</button>
            </div>
          </div>
        ))}
        {!skills.length && <div className="text-ios-label2 text-[13px]">未发现技能 (skills/ 目录为空)</div>}
      </div>

      {detail && (
        <Modal title={`${detail.name} · v${detail.version}`} onClose={() => setDetail(null)} wide>
          {/* C10: SKILL.md 正文按 Markdown 渲染 */}
          <div className="text-[13px] leading-6 selectable max-h-[46vh] overflow-auto
            [&_p]:my-1.5 [&_ul]:list-disc [&_li]:ml-4"
            dangerouslySetInnerHTML={{ __html: mdToHtml(detail.body || "") }} />
          {!detail.body && <div className="text-ios-label2 text-[13px]">(无说明)</div>}
          <div className="mt-4 pt-3 border-t border-black/5 dark:border-white/5">
            <div className="font-semibold text-[13px] mb-2">最近执行</div>
            {runs === null ? (
              <div className="text-[12.5px] text-ios-label2">加载中…</div>
            ) : !runs.length ? (
              <div className="text-[12.5px] text-ios-label2">暂无执行记录</div>
            ) : (
              <div className="space-y-1.5 max-h-[180px] overflow-auto">
                {runs.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-[12px]">
                    <span className={`px-1.5 py-0.5 rounded-full text-[10.5px] shrink-0
                      ${r.status === "ok" ? "bg-[#30D158]/15 text-[#30D158]" : "bg-[#FF453A]/15 text-[#FF453A]"}`}>
                      {r.status}
                    </span>
                    <span className="text-ios-label2 shrink-0">{(r.ts || "").slice(0, 19).replace("T", " ")}</span>
                    <span className="text-ios-label2 shrink-0">{r.ms} ms</span>
                    <span className="font-mono truncate text-ios-label2" title={JSON.stringify(r.args || {})}>
                      {JSON.stringify(r.args || {})}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}
      {/* C8: 写操作确认卡 —— 确认后携带 _confirmed 重新执行 */}
      {confirm && (
        <Modal title="写操作确认" onClose={() => setConfirm(null)}>
          <div className="text-[13px] leading-6">
            技能 <b>{confirm.skill.name}</b> 包含写入类操作, 执行前需要你确认。
            <div className="text-[12px] text-ios-label2 mt-1.5">{confirm.error}</div>
          </div>
          <div className="flex gap-2 mt-4 justify-end">
            <button className="ios-btn-ghost px-4 py-1.5 text-[13px]" onClick={() => setConfirm(null)}>取消</button>
            <button className="ios-btn-primary px-4 py-1.5 text-[13px]"
              onClick={() => { const s = confirm.skill; setConfirm(null); run(s, true); }}>确认执行</button>
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
