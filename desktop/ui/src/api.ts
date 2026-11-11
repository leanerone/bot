/* API 封装: 同源 Cookie 认证, 统一错误处理 */

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try { detail = (await resp.json()).detail || detail; } catch { /* ignore */ }
    const err = new Error(detail) as Error & { status?: number };
    err.status = resp.status;
    throw err;
  }
  return resp.json();
}

export interface Me { id: string; username: string; role: string; display_name: string }
export interface SessionMeta { id: string; title: string; updated_at: string; message_count: number;
  messages?: ChatMsg[]; hasMore?: boolean; oldestId?: number | null }
export interface DbMessage { id: number; role: string; type: string; content: string;
  sources?: Source[]; sql_text?: string; columns?: string[]; rows?: any[]; row_count?: number;
  rating?: string; created_at: string }
export interface Source { idx: number; source: string; score: number; excerpt?: string; text?: string }
export interface ChatMsg {
  role: "user" | "assistant";
  id?: number | null;
  type?: "kb" | "sql";
  text: string;
  sources?: Source[];
  sql?: string; columns?: string[]; rows?: any[]; row_count?: number;
  rating?: string | null;
  ts?: string;
  streaming?: boolean;
  error?: boolean;
}
export interface Health { status: string; kb_chunks: number; version: string;
  llm: { mock: boolean; model: string }; notes_mode: string }

export const getJSON = <T = any>(p: string) => api<T>(p);
export const postJSON = <T = any>(p: string, body?: any) =>
  api<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const patchJSON = <T = any>(p: string, body?: any) =>
  api<T>(p, { method: "PATCH", body: JSON.stringify(body) });
export const delJSON = <T = any>(p: string) => api<T>(p, { method: "DELETE" });
