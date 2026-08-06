/** 全网搜索面板（FR-3，异步任务化）：提交 ≤1s 受理 → 轮询任务状态 → 展示结果。 */

"use client";

import { useEffect, useRef, useState } from "react";
import {
  IMPORTANCE_LABELS,
  IMPORTANCE_STYLES,
  SOURCE_LABELS,
  SearchResultItem,
  clientFetch,
} from "@/lib/api";

type TaskStatus = {
  task_id: string;
  status: "queued" | "running" | "completed" | "failed";
  result?: SearchResultItem[] | null;
  error?: string | null;
};

const STATUS_LABELS: Record<string, string> = {
  queued: "排队中…",
  running: "正在聚合 Twitter + Bing 并送 AI 分析…",
};

export default function SearchPanel() {
  const [query, setQuery] = useState("");
  const [task, setTask] = useState<TaskStatus | null>(null);
  const [converted, setConverted] = useState(false);
  const [sort, setSort] = useState<"default" | "relevance">("default");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };
  useEffect(() => stopPolling, []);

  const doSearch = async () => {
    if (!query.trim()) return;
    stopPolling();
    setConverted(false);
    // ① 提交：立即返回 task_id（FR-3.2）
    const submitted = await clientFetch<TaskStatus>("/search", {
      method: "POST",
      body: JSON.stringify({ query: query.trim() }),
    });
    setTask(submitted);
    // ② 轮询任务状态
    timerRef.current = setInterval(async () => {
      try {
        const current = await clientFetch<TaskStatus>(`/search/${submitted.task_id}`);
        setTask(current);
        if (current.status === "completed" || current.status === "failed") {
          stopPolling();
        }
      } catch {
        stopPolling();
      }
    }, 2000);
  };

  const convertToKeyword = async () => {
    await clientFetch("/keywords", {
      method: "POST",
      body: JSON.stringify({ text: query.trim() }),
    });
    setConverted(true);
  };

  const results = task?.result ?? null;
  const sorted =
    sort === "relevance"
      ? [...(results ?? [])].sort((a, b) => (b.relevance ?? 0) - (a.relevance ?? 0))
      : (results ?? []);

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          doSearch();
        }}
        className="flex gap-2"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="临时搜一个还没监控的关键词…"
          className="flex-1 rounded-lg border border-[var(--card-border)] bg-[var(--card)] px-4 py-2.5 text-sm focus:border-[var(--accent)] focus:outline-none"
        />
        <button
          type="submit"
          disabled={!query.trim() || task?.status === "running" || task?.status === "queued"}
          className="rounded-lg bg-[var(--accent)] px-6 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          全网搜索
        </button>
      </form>

      {task && (task.status === "queued" || task.status === "running") && (
        <p className="text-sm text-[var(--muted)]">
          ⏳ {STATUS_LABELS[task.status]}
        </p>
      )}
      {task?.status === "failed" && (
        <p className="text-sm text-red-400">搜索失败：{task.error}</p>
      )}

      {task?.status === "completed" && results && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-[var(--muted)]">
            共 {results.length} 条结果（前 10 条附 AI 分析）
          </p>
          <div className="flex gap-2">
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as typeof sort)}
              className="rounded-lg border border-[var(--card-border)] bg-[var(--card)] px-3 py-1.5 text-sm"
            >
              <option value="default">默认排序</option>
              <option value="relevance">按相关性</option>
            </select>
            <button
              onClick={convertToKeyword}
              disabled={converted}
              className="rounded-lg border border-[var(--accent)]/40 px-4 py-1.5 text-sm text-[var(--accent)] hover:bg-[var(--accent)]/10 disabled:opacity-40"
            >
              {converted ? "✓ 已加入监控" : "+ 加入长期监控"}
            </button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {sorted.map((item) => (
          <article
            key={item.url}
            className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-4"
          >
            <div className="flex items-center gap-2 text-xs">
              <span className="rounded-full bg-zinc-500/15 px-2 py-0.5 text-zinc-300">
                {SOURCE_LABELS[item.source] ?? item.source}
              </span>
              {item.importance && (
                <span
                  className={`rounded-full border px-2 py-0.5 ${IMPORTANCE_STYLES[item.importance] ?? ""}`}
                >
                  {IMPORTANCE_LABELS[item.importance] ?? item.importance}
                </span>
              )}
              {item.relevance != null && (
                <span className="text-[var(--muted)]">相关性 {item.relevance}/100</span>
              )}
              {item.is_real === false && (
                <span className="rounded bg-yellow-500/15 px-1.5 py-0.5 text-yellow-400">
                  可疑
                </span>
              )}
            </div>
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 block font-medium hover:text-[var(--accent)]"
            >
              {item.title}
            </a>
            {item.summary && (
              <p className="mt-1 text-sm text-[var(--muted)]">AI 摘要：{item.summary}</p>
            )}
          </article>
        ))}
      </div>

      {task?.status === "completed" && results?.length === 0 && (
        <p className="py-12 text-center text-sm text-[var(--muted)]">
          没有找到相关内容，换个关键词试试
        </p>
      )}
    </div>
  );
}
