/**
 * 筛选排序栏（FR-2.4/2.5）：筛选条件全部映射 URL searchParams——
 * 刷新保持、可分享、服务端可预取（技术选型 §3.2 关键约定）。
 */

"use client";

import { useRouter, useSearchParams } from "next/navigation";

const SORTS = [
  { value: "latest", label: "最新" },
  { value: "published", label: "发布时间" },
  { value: "relevance", label: "相关性" },
  { value: "importance", label: "重要性" },
  { value: "hot", label: "热度" },
];

const RANGES = [
  { value: "", label: "全部时间" },
  { value: "1h", label: "1 小时" },
  { value: "today", label: "今天" },
  { value: "7d", label: "7 天" },
  { value: "30d", label: "30 天" },
];

const SOURCES = ["", "twitter", "weibo", "bilibili", "hackernews", "sogou", "bing"];
const SOURCE_NAMES: Record<string, string> = {
  "": "全部来源",
  twitter: "Twitter",
  weibo: "微博",
  bilibili: "B 站",
  hackernews: "HN",
  sogou: "搜狗",
  bing: "Bing",
};

const IMPORTANCES = [
  { value: "", label: "全部重要性" },
  { value: "urgent", label: "紧急" },
  { value: "high", label: "重要" },
  { value: "medium", label: "一般" },
  { value: "low", label: "低" },
];

export default function FilterSortBar() {
  const router = useRouter();
  const params = useSearchParams();

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("page"); // 筛选变化回到第一页
    router.push(`?${next.toString()}`);
  };

  const selectCls =
    "rounded-lg border border-[var(--card-border)] bg-[var(--card)] px-3 py-1.5 text-sm text-[var(--foreground)] focus:border-[var(--accent)] focus:outline-none";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        className={selectCls}
        value={params.get("source") ?? ""}
        onChange={(e) => setParam("source", e.target.value)}
      >
        {SOURCES.map((s) => (
          <option key={s} value={s}>
            {SOURCE_NAMES[s]}
          </option>
        ))}
      </select>
      <select
        className={selectCls}
        value={params.get("importance") ?? ""}
        onChange={(e) => setParam("importance", e.target.value)}
      >
        {IMPORTANCES.map((i) => (
          <option key={i.value} value={i.value}>
            {i.label}
          </option>
        ))}
      </select>
      <select
        className={selectCls}
        value={params.get("range") ?? ""}
        onChange={(e) => setParam("range", e.target.value)}
      >
        {RANGES.map((r) => (
          <option key={r.value} value={r.value}>
            {r.label}
          </option>
        ))}
      </select>
      <select
        className={selectCls}
        value={params.get("sort") ?? "latest"}
        onChange={(e) => setParam("sort", e.target.value)}
      >
        {SORTS.map((s) => (
          <option key={s.value} value={s.value}>
            排序：{s.label}
          </option>
        ))}
      </select>
    </div>
  );
}
