"use client";

import { useState } from "react";
import {
  HotspotRead,
  IMPORTANCE_LABELS,
  IMPORTANCE_STYLES,
  SOURCE_LABELS,
  relativeTime,
} from "@/lib/api";

/** 热度等级标签颜色（爆/热/温，R-403：由后端归一化分值驱动）—— 赛博霓虹配色 */
const HOT_LEVEL_STYLES: Record<string, string> = {
  爆: "bg-[rgba(255,45,120,0.15)] text-[var(--neon-pink)] shadow-[0_0_10px_rgba(255,45,120,0.25)]",
  热: "bg-orange-500/15 text-orange-400 shadow-[0_0_10px_rgba(251,146,60,0.2)]",
  温: "bg-[rgba(0,229,255,0.12)] text-[var(--accent)] shadow-[0_0_10px_rgba(0,229,255,0.2)]",
};

export default function HotspotCard({
  hotspot,
  onDelete,
}: {
  hotspot: HotspotRead;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [confirming, setConfirming] = useState(false);

  return (
    <article className="cyber-panel rounded-xl p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span
            className={`rounded-full border px-2 py-0.5 font-medium ${IMPORTANCE_STYLES[hotspot.importance] ?? IMPORTANCE_STYLES.low}`}
          >
            {IMPORTANCE_LABELS[hotspot.importance] ?? hotspot.importance}
          </span>
          <span className="rounded-full bg-zinc-500/15 px-2 py-0.5 text-zinc-300">
            {SOURCE_LABELS[hotspot.source] ?? hotspot.source}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 ${HOT_LEVEL_STYLES[hotspot.hot_level] ?? ""}`}
            title={`热度分 ${hotspot.hot_score_normalized}/100`}
          >
            {hotspot.hot_level} · {hotspot.hot_score_normalized}
          </span>
          {!hotspot.is_real && (
            <span className="rounded-full bg-yellow-500/15 px-2 py-0.5 text-yellow-400">
              可疑
            </span>
          )}
          {!hotspot.ai_reviewed && (
            <span className="rounded-full bg-zinc-500/15 px-2 py-0.5 text-zinc-500">
              未经 AI 审核
            </span>
          )}
        </div>
        <span className="shrink-0 text-xs text-[var(--muted)]">
          {relativeTime(hotspot.published_at ?? hotspot.created_at)}
        </span>
      </div>

      <a
        href={hotspot.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 block text-base font-semibold leading-snug hover:text-[var(--accent)]"
      >
        {hotspot.title}
      </a>

      {hotspot.summary && (
        <p className="mt-2 text-sm text-[var(--muted)]">
          <span className="mr-1 rounded bg-[var(--accent)]/15 px-1 text-xs text-[var(--accent)]">
            AI 摘要
          </span>
          {hotspot.summary}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-[var(--muted)]">
        {hotspot.author_name && (
          <span>
            {hotspot.author_name}
            {hotspot.author_verified && <span className="ml-0.5 text-sky-400">✓</span>}
          </span>
        )}
        <span>相关性 {hotspot.relevance}/100</span>
        {hotspot.like_count != null && <span>👍 {hotspot.like_count}</span>}
        {hotspot.view_count != null && <span>👁 {hotspot.view_count}</span>}
        {hotspot.retweet_count != null && <span>🔁 {hotspot.retweet_count}</span>}
        {hotspot.comment_count != null && <span>💬 {hotspot.comment_count}</span>}
        {hotspot.keyword_text && (
          <span className="rounded bg-[var(--accent)]/10 px-1.5 py-0.5 text-[var(--accent)]">
            {hotspot.keyword_text}
          </span>
        )}

        <span className="ml-auto flex gap-3">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="hover:text-[var(--foreground)]"
          >
            {expanded ? "收起 ▲" : "展开 ▼"}
          </button>
          {confirming ? (
            <>
              <button
                onClick={() => onDelete(hotspot.id)}
                className="text-red-400 hover:text-red-300"
              >
                确认删除
              </button>
              <button onClick={() => setConfirming(false)}>取消</button>
            </>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              className="text-zinc-500 hover:text-red-400"
            >
              删除
            </button>
          )}
        </span>
      </div>

      {expanded && (
        <div className="mt-4 space-y-3 border-t border-[var(--card-border)] pt-4 text-sm">
          {hotspot.relevance_reason && (
            <p className="text-[var(--muted)]">
              <span className="text-[var(--foreground)]">AI 打分理由：</span>
              {hotspot.relevance_reason}
            </p>
          )}
          <p className="max-h-48 overflow-y-auto whitespace-pre-wrap text-[var(--muted)]">
            {hotspot.content || "（无正文）"}
          </p>
        </div>
      )}
    </article>
  );
}
