/** 全网搜索页（FR-3）：纯 Client（交互密集，无 SSR 价值，技术选型 §3.1）。 */

import SearchPanel from "@/components/search-panel";

export default function SearchPage() {
  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 px-8 py-8">
      <div>
        <p className="cyber-label">Deep Scan // Ad-hoc Query</p>
        <h1 className="neon-text mt-1 text-3xl font-bold tracking-wide">全网搜索</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          临时搜一个还没监控的关键词，Twitter + Bing 聚合并附 AI 判断
        </p>
      </div>
      <SearchPanel />
    </main>
  );
}
