/** 立即检查进度弹窗（FR-7.3 增强）：
 *
 * - 点击「立即检查」后立即弹出，轮询期间实时展示逐词进度；
 * - 已完成的关键词展示采集/候选/分析/新增数量，可点击「查看」跳到首页按该关键词筛选热点；
 * - 检查结束后保留总结，手动关闭；运行中关闭弹窗不中断后台检查。
 */

"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clientFetch, KeywordRead } from "@/lib/api";

export type KeywordReportItem = {
  keyword: string;
  keyword_id: string;
  collected: number;
  candidates: number;
  analyzed: number;
  created: number;
  errors: string[];
};

export type CheckStatus = {
  running: boolean;
  run_id: string | null;
  total_keywords: number;
  done_keywords: number;
  current_keyword: string | null;
  hotspots_created: number;
  ai_calls: number;
  reports: KeywordReportItem[];
};

export default function CheckProgressModal({
  status,
  onClose,
}: {
  status: CheckStatus | null;
  onClose: () => void;
}) {
  const router = useRouter();
  const [keywords, setKeywords] = useState<KeywordRead[]>([]);

  // 打开时拉一次关键词清单，用于列出「待办」项
  useEffect(() => {
    clientFetch<KeywordRead[]>("/keywords")
      .then((ks) => setKeywords(ks.filter((k) => k.is_active)))
      .catch(() => {});
  }, []);

  const running = status?.running ?? false;
  const total = status?.total_keywords ?? 0;
  const done = status?.done_keywords ?? 0;
  const reports = status?.reports ?? [];
  const doneIds = new Set(reports.map((r) => r.keyword_id));
  const pending = keywords.filter(
    (k) => !doneIds.has(k.id) && k.text !== status?.current_keyword
  );
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  const viewKeyword = (keywordId: string) => {
    onClose();
    router.push(`/?keyword_id=${keywordId}`);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-2xl border border-[var(--accent)]/25 bg-[rgba(6,10,22,0.95)] shadow-[0_0_56px_rgba(0,229,255,0.18)] backdrop-blur-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between border-b border-[var(--card-border)] px-5 py-4">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo.png"
              alt=""
              className="h-9 w-9 rounded-lg shadow-[0_0_12px_rgba(0,229,255,0.3)]"
            />
            <div>
              <p className="cyber-label">{running ? "Scanning //" : "Complete //"}</p>
              <h2 className="neon-text mt-0.5 text-base font-semibold">
                {running ? "热点检查进行中" : "本轮检查完成"}
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-lg leading-none text-[var(--muted)] hover:bg-[var(--background)] hover:text-[var(--foreground)]"
            aria-label="关闭"
          >
            ×
          </button>
        </div>

        {/* 进度条 */}
        <div className="border-b border-[var(--card-border)] px-5 py-4">
          <div className="flex items-center justify-between text-xs text-[var(--muted)]">
            <span>
              关键词进度 {done}/{total}
              {status?.current_keyword && running
                ? ` · 正在分析：${status.current_keyword}`
                : ""}
            </span>
            <span>{pct}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--background)]">
            <div
              className="h-full rounded-full bg-[var(--accent)] shadow-[0_0_12px_var(--accent-glow)] transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* 逐词清单 */}
        <div className="min-h-24 flex-1 overflow-y-auto px-5 py-3">
          {reports.length === 0 && !status?.current_keyword && (
            <p className="py-6 text-center text-sm text-[var(--muted)]">
              {running ? "正在启动，准备采集…" : "暂无本轮报告"}
            </p>
          )}
          <ul className="space-y-2">
            {reports.map((r) => (
              <li
                key={r.keyword_id || r.keyword}
                className="flex items-center gap-3 rounded-lg border border-[var(--card-border)] px-3 py-2 text-sm"
              >
                <span className={r.errors.length ? "text-red-400" : "text-emerald-400"}>
                  {r.errors.length ? "✗" : "✓"}
                </span>
                <span className="min-w-0 flex-1 truncate font-medium">{r.keyword}</span>
                <span className="shrink-0 text-xs text-[var(--muted)]">
                  采集 {r.collected} · 候选 {r.candidates} · 新增{" "}
                  <span className={r.created > 0 ? "text-[var(--accent)]" : ""}>
                    {r.created}
                  </span>
                </span>
                {r.keyword_id && (
                  <button
                    onClick={() => viewKeyword(r.keyword_id)}
                    className="neon-btn shrink-0 rounded-md px-2 py-0.5 text-xs"
                  >
                    查看
                  </button>
                )}
              </li>
            ))}
            {running && status?.current_keyword && (
              <li className="flex items-center gap-3 rounded-lg border border-[var(--accent)]/30 px-3 py-2 text-sm">
                <span className="animate-pulse text-[var(--accent)]">⏳</span>
                <span className="min-w-0 flex-1 truncate font-medium">
                  {status.current_keyword}
                </span>
                <span className="shrink-0 text-xs text-[var(--accent)]">分析中…</span>
              </li>
            )}
            {running &&
              pending.map((k) => (
                <li
                  key={k.id}
                  className="flex items-center gap-3 rounded-lg border border-dashed border-[var(--card-border)] px-3 py-2 text-sm text-[var(--muted)]"
                >
                  <span>○</span>
                  <span className="min-w-0 flex-1 truncate">{k.text}</span>
                  <span className="shrink-0 text-xs">等待中</span>
                </li>
              ))}
          </ul>
        </div>

        {/* 底部总结 */}
        <div className="flex items-center justify-between border-t border-[var(--card-border)] px-5 py-3 text-xs text-[var(--muted)]">
          <span>
            AI 调用 {status?.ai_calls ?? 0} 次 · 新增热点{" "}
            <span className="text-[var(--accent)]">{status?.hotspots_created ?? 0}</span> 条
          </span>
          {!running && (
            <button
              onClick={onClose}
              className="rounded-lg border border-[var(--card-border)] px-3 py-1.5 text-[var(--foreground)] hover:bg-[var(--background)]"
            >
              关闭
            </button>
          )}
          {running && <span>关闭弹窗不影响后台检查</span>}
        </div>
      </div>
    </div>
  );
}
