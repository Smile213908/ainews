/** 数据源健康面板页（FR-6）：RSC 首屏 + 30s 轮询刷新。 */

import SourceHealthPanel from "@/components/source-health-panel";
import { SourceHealthRead, serverFetch } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SourcesPage() {
  const health = await serverFetch<SourceHealthRead[]>("/api/sources/health");

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <div>
        <h1 className="text-2xl font-bold">数据源健康</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          连续失败 ≥3 轮的源会标红并产生告警通知（每 30 秒自动刷新）
        </p>
      </div>
      <SourceHealthPanel initialData={health} />
    </main>
  );
}
