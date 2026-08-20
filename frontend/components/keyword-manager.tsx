/** 关键词管理（FR-1）：创建/激活暂停/编辑/删除，删除二次确认。 */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { KeywordRead, clientFetch, relativeTime } from "@/lib/api";

type CheckStatus = { running: boolean; hotspots_created: number };

export default function KeywordManager({ initialData }: { initialData: KeywordRead[] }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [checkState, setCheckState] = useState<Record<string, string>>({});
  const timers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  useEffect(() => {
    const current = timers.current;
    return () => Object.values(current).forEach(clearInterval);
  }, []);

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

  /** 立即检查：触发后每 3s 轮询全局检查状态，结束后刷新计数并提示结果（FR-7.3） */
  const startCheck = async (kw: KeywordRead) => {
    setCheckState((s) => ({ ...s, [kw.id]: "检查中…" }));
    try {
      await clientFetch(`/keywords/${kw.id}/check`, { method: "POST" });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setCheckState((s) => ({
        ...s,
        [kw.id]: msg.includes("返回 409") ? "已有检查进行中，稍后再试" : "触发失败，稍后再试",
      }));
      return;
    }
    timers.current[kw.id] = setInterval(async () => {
      try {
        const st = await clientFetch<CheckStatus>("/check-hotspots/status");
        if (!st.running) {
          clearInterval(timers.current[kw.id]);
          delete timers.current[kw.id];
          setCheckState((s) => ({
            ...s,
            [kw.id]: `完成，新增 ${st.hotspots_created} 条热点`,
          }));
          invalidate();
        }
      } catch {
        /* 单次轮询失败忽略，下一轮重试 */
      }
    }, 3000);
  };

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
          className="neon-btn rounded-lg px-5 py-2 text-sm font-medium"
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
            className="cyber-panel flex items-center justify-between rounded-xl p-4"
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
                {checkState[kw.id] && (
                  <span className="ml-2 text-[var(--accent)]">{checkState[kw.id]}</span>
                )}
              </p>
            </div>
            <div className="flex gap-2 text-xs">
              <button
                onClick={() => startCheck(kw)}
                disabled={checkState[kw.id] === "检查中…"}
                className="neon-btn rounded-lg px-3 py-1.5"
              >
                {checkState[kw.id] === "检查中…" ? "检查中…" : "立即检查"}
              </button>
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
