/** 全网搜索页（FR-3）：纯 Client（交互密集，无 SSR 价值，技术选型 §3.1）。 */

import SearchPanel from "@/components/search-panel";

export default function SearchPage() {
  return (
    <main className="mx-auto max-w-4xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-2xl font-bold">全网搜索</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          临时搜一个还没监控的关键词，Twitter + Bing 聚合并附 AI 判断
        </p>
      </div>
      <SearchPanel />
    </main>
  );
}
