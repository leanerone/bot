import React, { useEffect, useState } from "react";
import { Me, getJSON, postJSON, delJSON } from "../api";
import { BigTitle, Card, Modal, Spinner } from "../components/ui";

interface SrcInfo { source: string; chunks: number }

export default function Knowledge({ me }: { me: Me }) {
  const [sources, setSources] = useState<SrcInfo[]>([]);
  const [kbChunks, setKbChunks] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState("");
  const [preview, setPreview] = useState<{ name: string; chunks: { text: string }[] } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const admin = me.role === "admin";

  const refresh = async () => {
    const h = await getJSON("/api/health"); setKbChunks(h.kb_chunks);
    if (admin) { const r = await getJSON<{ sources: SrcInfo[] }>("/api/admin/kb/sources"); setSources(r.sources); }
  };
  useEffect(() => { refresh(); }, []);

  const run = async (label: string, fn: () => Promise<any>) => {
    setBusy(label); setResult("");
    try { const j = await fn(); setResult(JSON.stringify(j, null, 2)); refresh(); }
    catch (e: any) { setResult("失败: " + e.message); }
    finally { setBusy(""); }
  };

  const ingest = () => run("导入常规文档", () => postJSON("/api/kb/ingest"));
  const ingestNotes = () => run("导入 Notes 导出", () => postJSON("/api/kb/ingest_notes", { mode: "export" }));
  const rebuild = () => { if (confirm("确认全量重建知识库？")) run("全量重建", () => postJSON("/api/admin/kb/rebuild")); };
  const delSource = async (name: string) => {
    if (!confirm(`确认从知识库摘除「${name}」？`)) return;
    const r = await delJSON(`/api/admin/kb/sources?name=${encodeURIComponent(name)}`);
    setResult(JSON.stringify(r, null, 2)); refresh();
  };
  const viewSource = async (name: string) => {
    const j = await getJSON(`/api/admin/kb/source-chunks?name=${encodeURIComponent(name)}`);
    setPreview({ name, chunks: j.chunks });
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const files = [...e.dataTransfer.files];
    if (!files.length) return;
    setBusy("上传文件");
    const form = new FormData();
    files.forEach(f => form.append("files", f));
    fetch("/api/kb/upload", { method: "POST", body: form })
      .then(r => r.json()).then(j => { setResult(JSON.stringify(j, null, 2)); refresh(); })
      .catch(e => setResult("上传失败: " + e.message))
      .finally(() => setBusy(""));
  };

  return (
    <div className="h-full overflow-y-auto px-6 pt-[46px] pb-6">
      <BigTitle sub="SOP / 手册 / HCL Notes 导出的统一入口，导入即检索">知识库</BigTitle>

      <div className={`rounded-[16px] border-2 border-dashed p-8 text-center transition-colors
        ${dragOver ? "border-[#0A84FF] bg-[#0A84FF]/5" : "border-black/15 dark:border-white/15"}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}>
        <div className="text-[34px] mb-1">📥</div>
        <div className="text-[15px] font-semibold">拖拽文档到这里导入知识库</div>
        <div className="text-[12px] text-ios-label2 mt-1">支持 .md / .txt / .docx / .pdf，重复导入自动去重</div>
        {busy && <div className="mt-3 grid place-items-center"><Spinner text={busy + "…"} /></div>}
      </div>

      <div className="grid grid-cols-4 gap-2.5 my-4">
        <button className="ios-btn-primary py-2" disabled={!!busy} onClick={ingest}>导入常规文档</button>
        <button className="ios-btn-primary py-2" disabled={!!busy} onClick={ingestNotes}>导入 Notes 导出</button>
        <button className="ios-btn-ghost py-2" onClick={refresh}>刷新统计</button>
        {admin && <button className="ios-btn-ghost py-2 !text-[#FF453A]" disabled={!!busy} onClick={rebuild}>全量重建</button>}
      </div>

      {result && <pre className="bg-black/[.03] dark:bg-white/[.05] rounded-[12px] p-3.5 text-[12px] overflow-auto max-h-[200px] mb-4">{result}</pre>}

      <div className="ios-section-title">来源清单 {kbChunks !== null && `· 共 ${kbChunks} 片段`}</div>
      <Card className="overflow-hidden p-0">
        <table className="w-full text-[13px]">
          <thead><tr className="text-left text-ios-label2">
            <th className="px-4 py-2.5 font-semibold">来源</th>
            <th className="px-4 py-2.5 font-semibold">片段数</th>
            <th className="px-4 py-2.5 font-semibold w-[160px]">操作</th>
          </tr></thead>
          <tbody>
            {sources.map(s => (
              <tr key={s.source} className="border-t border-black/5 dark:border-white/5">
                <td className="px-4 py-2.5 break-all">{s.source}</td>
                <td className="px-4 py-2.5">{s.chunks}</td>
                <td className="px-4 py-2.5 flex gap-2">
                  <button className="ios-btn-ghost !py-1 !px-2.5 text-[12px]" onClick={() => viewSource(s.source)}>查看</button>
                  {admin && <button className="ios-btn-ghost !py-1 !px-2.5 text-[12px] !text-[#FF453A]"
                    onClick={() => delSource(s.source)}>摘除</button>}
                </td>
              </tr>
            ))}
            {!sources.length && <tr><td colSpan={3} className="px-4 py-4 text-ios-label2 text-center">
              {admin ? "(暂无来源 — 先导入文档)" : "(仅 admin 可见来源治理)"}</td></tr>}
          </tbody>
        </table>
      </Card>

      {preview && (
        <Modal title={`${preview.name} · ${preview.chunks.length} 片段`} onClose={() => setPreview(null)} wide>
          <pre className="whitespace-pre-wrap text-[13px] leading-6 bg-black/[.03] dark:bg-white/[.05] rounded-[10px] p-3.5 max-h-[55vh] overflow-auto">
            {preview.chunks.map((c, i) => `── 片段 ${i + 1} ──\n${c.text}`).join("\n\n")}
          </pre>
        </Modal>
      )}
    </div>
  );
}
