/** 关键词管理页（FR-1）：RSC 列表 + Client 表单（读多写少）。 */

import KeywordManager from "@/components/keyword-manager";
import { KeywordRead, serverFetch } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function KeywordsPage() {
  const keywords = await serverFetch<KeywordRead[]>("/api/keywords");

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 px-8 py-8">
      <div>
        <p className="cyber-label">Keyword Matrix // Watchlist</p>
        <h1 className="neon-text mt-1 text-3xl font-bold tracking-wide">关键词管理</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          系统每 30 分钟对所有「监控中」的关键词执行一轮全网检查
        </p>
      </div>
      <KeywordManager initialData={keywords} />
    </main>
  );
}
