/**
 * Dashboard（FR-2）：RSC 首屏 SSR 直出统计与首屏热点列表，
 * Client 侧 TanStack Query 接管筛选/分页/实时更新。
 */

import { Suspense } from "react";
import CheckTrigger from "@/components/check-trigger";
import FilterSortBar from "@/components/filter-sort-bar";
import HotspotFeed from "@/components/hotspot-feed";
import NotificationBell from "@/components/notification-bell";
import StatsHero from "@/components/stats-hero";
import { HotspotPage, HotspotStats, serverFetch } from "@/lib/api";

export const dynamic = "force-dynamic"; // 首屏数据实时取

function wsUrl(): string {
  const base = (process.env.API_BASE_URL ?? "http://localhost:8000").replace(
    /^http/,
    "ws"
  );
  return `${base}/ws?api_key=${process.env.API_KEY ?? ""}`;
}

export default async function DashboardPage() {
  const [stats, feed] = await Promise.all([
    serverFetch<HotspotStats>("/api/hotspots/stats"),
    serverFetch<HotspotPage>("/api/hotspots?page_size=20"),
  ]);

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">热点信息流</h1>
        <div className="flex items-center gap-4">
          <CheckTrigger />
          <NotificationBell wsUrl={wsUrl()} />
        </div>
      </div>
      <StatsHero stats={stats} />
      <Suspense fallback={<p className="text-sm text-[var(--muted)]">加载筛选…</p>}>
        <FilterSortBar />
      </Suspense>
      <Suspense fallback={<p className="text-sm text-[var(--muted)]">加载热点…</p>}>
        <HotspotFeed initialData={feed} wsUrl={wsUrl()} />
      </Suspense>
    </main>
  );
}
