// 与 qwenpaw-pet/frontend/src/index.tsx 中的实现保持一致。
//
// 浏览器通过 window.QwenPaw.host.getApiUrl 拿到当前控制台的后端基址
// （开发态是 Vite 代理后的 8088，生产态是同源），避免把后端地址硬编
// 码进 bundle。Authorization + X-Agent-Id 头由 authHeaders() 注入，
// 缺 X-Agent-Id 时 QwenPaw 网关会把请求路由到默认 agent，多 agent
// 场景下会"静默地"走错 agent。

import type * as ReactNS from "react";

const host = window.QwenPaw.host;
const getApiUrl = host.getApiUrl;
const getApiToken = host.getApiToken;

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const t = getApiToken?.();
  if (t) headers.Authorization = `Bearer ${t}`;
  try {
    const agentStorage =
      sessionStorage.getItem("qwenpaw-agent-storage") ||
      localStorage.getItem("qwenpaw-agent-storage");
    if (agentStorage) {
      const parsed = JSON.parse(agentStorage);
      const selectedAgent = parsed?.state?.selectedAgent;
      if (selectedAgent) {
        headers["X-Agent-Id"] = selectedAgent;
      }
    }
  } catch (e) {
    // 静默失败：缺 X-Agent-Id 不会让请求失败，只会让网关用默认 agent
    console.warn("Failed to read selected agent from storage:", e);
  }
  return headers;
}

async function request(path: string, init: RequestInit = {}): Promise<unknown> {
  const res = await fetch(getApiUrl(path), {
    ...init,
    headers: { ...authHeaders(), ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${await res.text()}`);
  }
  return res.json();
}

export async function apiGet(path: string): Promise<unknown> {
  return request(path);
}

export async function apiPost(path: string, body: unknown): Promise<unknown> {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function apiDelete(path: string): Promise<unknown> {
  return request(path, { method: "DELETE" });
}

export async function apiPut(path: string, body: unknown): Promise<unknown> {
  return request(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// 重新导出 React 命名空间，方便页面组件统一 import。
export type { ReactNS };
