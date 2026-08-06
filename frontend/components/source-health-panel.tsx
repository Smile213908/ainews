/** 数据源健康面板（FR-6）：6 源状态卡，连续失败 ≥3 标红。 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { SourceHealthRead, clientFetch, relativeTime } from "@/lib/api";

const ALL_SOURCES = [
  { key: "twitter", label: "Twitter", desc: "twitterapi.io 第三方 API" },
  { key: "weibo", label: "微博热搜", desc: "热搜榜双向包含匹配" },
  { key: "bilibili", label: "B 站", desc: "公开 API + UP 主检测" },
  { key: "hackernews", label: "HackerNews", desc: "Algolia 官方 API" },
  { key: "sogou", label: "搜狗", desc: "HTML 爬虫" },
  { key: "bing", label: "Bing", desc: "HTML 爬虫" },
];

export default function SourceHealthPanel({
  initialData,
}: {
  initialData: SourceHealthRead[];
}) {
  const { data } = useQuery({
    queryKey: ["sources-health"],
    queryFn: () => clientFetch<SourceHealthRead[]>("/sources/health"),
    initialData,
    refetchInterval: 30_000,
  });

  const bySource = new Map((data ?? []).map((s) => [s.source, s]));

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {ALL_SOURCES.map(({ key, label, desc }) => {
        const health = bySource.get(key);
        const failures = health?.consecutive_failures ?? 0;
        const state = !health
          ? { text: "尚未运行", cls: "bg-zinc-500/15 text-zinc-400" }
          : failures >= 3
            ? { text: "异常", cls: "bg-red-500/15 text-red-400" }
            : failures > 0
              ? { text: "波动", cls: "bg-yellow-500/15 text-yellow-400" }
              : { text: "正常", cls: "bg-emerald-500/15 text-emerald-400" };

        return (
          <div
            key={key}
            className={`rounded-xl border p-5 ${
              failures >= 3
                ? "border-red-500/40 bg-red-500/5"
                : "border-[var(--card-border)] bg-[var(--card)]"
            }`}
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold">{label}</h3>
                <p className="text-xs text-[var(--muted)]">{desc}</p>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${state.cls}`}>
                {state.text}
              </span>
            </div>
            <dl className="mt-4 space-y-1.5 text-xs text-[var(--muted)]">
              <div className="flex justify-between">
                <dt>最近成功</dt>
                <dd>{relativeTime(health?.last_success_at ?? null)}</dd>
              </div>
              <div className="flex justify-between">
                <dt>连续失败</dt>
                <dd className={failures > 0 ? "text-red-400" : ""}>{failures} 轮</dd>
              </div>
              {health?.last_error && (
                <div className="pt-1">
                  <dt className="mb-0.5">最近错误</dt>
                  <dd className="line-clamp-2 break-all rounded bg-black/30 p-2 font-mono text-[11px] text-red-300">
                    {health.last_error}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        );
      })}
    </div>
  );
}
