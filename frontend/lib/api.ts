/**
 * API 访问层（ADR-8：类型由 openapi-typescript 从后端契约生成）。
 *
 * - serverFetch：RSC / Route Handler 服务端直连后端，携带 API Key；
 * - 浏览器端一律走 /api/bff 代理（Key 不下发浏览器，技术选型 §8.1）。
 */

import type { components } from "./api-types";

const BASE = process.env.API_BASE_URL ?? "http://localhost:8000";
const KEY = process.env.API_KEY ?? "";

export type HotspotRead = components["schemas"]["HotspotRead"];
export type HotspotPage = components["schemas"]["HotspotPage"];
export type HotspotStats = components["schemas"]["HotspotStats"];
export type KeywordRead = components["schemas"]["KeywordRead"];
export type NotificationRead = components["schemas"]["NotificationRead"];
export type SourceHealthRead = components["schemas"]["SourceHealthRead"];
export type SearchResultItem = components["schemas"]["SearchResultItem"];

export async function serverFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "X-API-Key": KEY, "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!resp.ok) {
    throw new Error(`API ${path} 返回 ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

/** 浏览器端：经 BFF 代理 */
export async function clientFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`/api/bff${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "");
    throw new Error(`API ${path} 返回 ${resp.status}: ${detail.slice(0, 200)}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

/** 相对时间格式化（FR-2.2） */
export function relativeTime(iso: string | null): string {
  if (!iso) return "时间未知";
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return new Date(iso).toLocaleDateString("zh-CN");
}

export const SOURCE_LABELS: Record<string, string> = {
  twitter: "Twitter",
  weibo: "微博热搜",
  bilibili: "B 站",
  hackernews: "HackerNews",
  sogou: "搜狗",
  bing: "Bing",
};

export const IMPORTANCE_STYLES: Record<string, string> = {
  urgent: "bg-red-500/15 text-red-400 border-red-500/30",
  high: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  medium: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  low: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

export const IMPORTANCE_LABELS: Record<string, string> = {
  urgent: "紧急",
  high: "重要",
  medium: "一般",
  low: "低",
};
