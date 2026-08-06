/**
 * 热点信息流（FR-2）：TanStack Query 管理服务端状态，queryKey 与 URL 同步；
 * 收到 WS hotspot:new → 失效重取 + toast（FR-2.6）。
 */

"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";
import HotspotCard from "@/components/hotspot-card";
import { HotspotPage, clientFetch } from "@/lib/api";
import { useHotspotSocket } from "@/hooks/use-hotspot-socket";

export default function HotspotFeed({
  initialData,
  wsUrl,
}: {
  initialData: HotspotPage;
  wsUrl: string;
}) {
  const params = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<string | null>(null);

  const qs = params.toString();
  const queryKey = ["hotspots", qs];

  const { data, isFetching } = useQuery({
    queryKey,
    queryFn: () => clientFetch<HotspotPage>(`/hotspots?${qs}`),
    initialData: qs === "" ? initialData : undefined,
    placeholderData: (prev) => prev,
  });

  const refresh = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ["hotspots"] }),
    [queryClient]
  );

  useHotspotSocket({
    wsUrl,
    onEvent: (e) => {
      if (e.event === "hotspot:new") {
        setToast(`新热点：${String(e.data.title ?? "").slice(0, 40)}`);
        setTimeout(() => setToast(null), 4000);
        refresh();
      }
    },
    onReconnect: refresh, // 重连后全量刷新一次（FR-2.6）
  });

  const page = data?.page ?? 1;
  const totalPages = data?.total_pages ?? 0;

  const gotoPage = (p: number) => {
    const next = new URLSearchParams(qs);
    next.set("page", String(p));
    router.push(`?${next.toString()}`);
  };

  const onDelete = async (id: string) => {
    await clientFetch(`/hotspots/${id}`, { method: "DELETE" });
    refresh();
  };

  return (
    <div className="space-y-4">
      {toast && (
        <div className="fixed right-6 top-6 z-50 rounded-lg border border-[var(--accent)]/40 bg-[var(--card)] px-4 py-3 text-sm shadow-lg shadow-[var(--accent-glow)]">
          🔔 {toast}
        </div>
      )}

      {isFetching && <p className="text-xs text-[var(--muted)]">刷新中…</p>}

      {data?.items.length === 0 && (
        <div className="rounded-xl border border-dashed border-[var(--card-border)] p-12 text-center text-[var(--muted)]">
          <p className="text-lg">监控中</p>
          <p className="mt-2 text-sm">系统每 30 分钟检查一轮，发现热点会实时推送到这里</p>
        </div>
      )}

      {data?.items.map((h) => <HotspotCard key={h.id} hotspot={h} onDelete={onDelete} />)}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4 text-sm">
          <button
            disabled={page <= 1}
            onClick={() => gotoPage(page - 1)}
            className="rounded-lg border border-[var(--card-border)] px-3 py-1.5 disabled:opacity-30"
          >
            上一页
          </button>
          <span className="text-[var(--muted)]">
            第 {page} / {totalPages} 页 · 共 {data?.total} 条
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => gotoPage(page + 1)}
            className="rounded-lg border border-[var(--card-border)] px-3 py-1.5 disabled:opacity-30"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
