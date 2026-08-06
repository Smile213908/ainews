/** 关键词管理（FR-1）：创建/激活暂停/编辑/删除，删除二次确认。 */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { KeywordRead, clientFetch, relativeTime } from "@/lib/api";

export default function KeywordManager({ initialData }: { initialData: KeywordRead[] }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const { data: keywords } = useQuery({
    queryKey: ["keywords"],
    queryFn: () => clientFetch<KeywordRead[]>("/keywords"),
    initialData,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["keywords"] });

  const createMutation = useMutation({
    mutationFn: () =>
      clientFetch<KeywordRead>("/keywords", {
        method: "POST",
        body: JSON.stringify({ text, category: category || null }),
      }),
    onSuccess: () => {
      setText("");
      setCategory("");
      setError(null);
      invalidate();
    },
    onError: (e) => setError(e.message.includes("409") ? "关键词已存在" : e.message),
  });

  const toggleMutation = useMutation({
    mutationFn: (id: string) =>
      clientFetch<KeywordRead>(`/keywords/${id}/toggle`, { method: "PATCH" }),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => clientFetch(`/keywords/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setConfirmId(null);
      invalidate();
    },
  });

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) createMutation.mutate();
        }}
        className="flex flex-wrap gap-2"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="输入关键词，如：Kimi、DeepSeek、某 UP 主名"
          className="min-w-64 flex-1 rounded-lg border border-[var(--card-border)] bg-[var(--card)] px-4 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
        />
        <input
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder="分类（可选）"
          className="w-32 rounded-lg border border-[var(--card-border)] bg-[var(--card)] px-4 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
        />
        <button
          type="submit"
          disabled={createMutation.isPending || !text.trim()}
          className="rounded-lg bg-[var(--accent)] px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          添加监控
        </button>
      </form>
      {error && <p className="text-sm text-red-400">{error}</p>}

      {keywords?.length === 0 && (
        <div className="rounded-xl border border-dashed border-[var(--card-border)] p-12 text-center text-[var(--muted)]">
          <p className="text-lg">还没有监控关键词</p>
          <p className="mt-2 text-sm">添加第一个关键词，系统就会开始 7×24 全网监控</p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {keywords?.map((kw) => (
          <div
            key={kw.id}
            className="flex items-center justify-between rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-4"
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold">{kw.text}</span>
                {kw.category && (
                  <span className="rounded bg-zinc-500/15 px-1.5 py-0.5 text-xs text-zinc-400">
                    {kw.category}
                  </span>
                )}
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    kw.is_active
                      ? "bg-emerald-500/15 text-emerald-400"
                      : "bg-zinc-500/15 text-zinc-500"
                  }`}
                >
                  {kw.is_active ? "监控中" : "已暂停"}
                </span>
              </div>
              <p className="mt-1 text-xs text-[var(--muted)]">
                累计 {kw.hotspot_count} 条热点 · 创建于 {relativeTime(kw.created_at)}
              </p>
            </div>
            <div className="flex gap-2 text-xs">
              <button
                onClick={() => toggleMutation.mutate(kw.id)}
                className="rounded-lg border border-[var(--card-border)] px-3 py-1.5 hover:border-[var(--accent)]/40"
              >
                {kw.is_active ? "暂停" : "激活"}
              </button>
              {confirmId === kw.id ? (
                <>
                  <button
                    onClick={() => deleteMutation.mutate(kw.id)}
                    className="rounded-lg bg-red-500/80 px-3 py-1.5 text-white"
                  >
                    确认删除
                  </button>
                  <button
                    onClick={() => setConfirmId(null)}
                    className="rounded-lg border border-[var(--card-border)] px-3 py-1.5"
                  >
                    取消
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setConfirmId(kw.id)}
                  className="rounded-lg border border-[var(--card-border)] px-3 py-1.5 text-zinc-500 hover:text-red-400"
                >
                  删除
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
