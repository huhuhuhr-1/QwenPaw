import type { TodoItem } from "./types";

function getSelectedAgentId(): string | null {
  try {
    const raw =
      window.sessionStorage?.getItem("qwenpaw-agent-storage") ??
      window.localStorage?.getItem("qwenpaw-agent-storage");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const selected = parsed?.state?.selectedAgent;
    return typeof selected === "string" && selected ? selected : null;
  } catch {
    return null;
  }
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const t = window.QwenPaw.host.getApiToken?.();
  if (t) headers.Authorization = `Bearer ${t}`;
  const agentId = getSelectedAgentId();
  if (agentId) headers["X-Agent-Id"] = agentId;
  return headers;
}

export interface ListParams {
  status?: string;
  keyword?: string;
  time_from?: number;
  time_to?: number;
  limit?: number;
  offset?: number;
}

export async function listTodos(params: ListParams = {}): Promise<{ items: TodoItem[] }> {
  const sp = new URLSearchParams();
  if (params.status && params.status !== "all") sp.set("status", params.status);
  if (params.keyword) sp.set("keyword", params.keyword);
  if (params.time_from != null) sp.set("time_from", String(params.time_from));
  if (params.time_to != null) sp.set("time_to", String(params.time_to));
  if (params.limit != null) sp.set("limit", String(params.limit));
  if (params.offset != null) sp.set("offset", String(params.offset));

  const qs = sp.toString();
  const url = window.QwenPaw.host.getApiUrl(`/todo/${qs ? `?${qs}` : ""}`);
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export async function updateTodoStatus(taskId: string, status: string): Promise<void> {
  const url = window.QwenPaw.host.getApiUrl(`/todo/${taskId}`);
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
}
