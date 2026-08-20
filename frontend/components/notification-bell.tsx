"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NotificationRead, clientFetch } from "@/lib/api";
import { useHotspotSocket } from "@/hooks/use-hotspot-socket";

/** 通知铃铛（FR-4）：未读角标 + 下拉面板 + WS 实时 +1 */
export default function NotificationBell({ wsUrl }: { wsUrl: string }) {
  const [open, setOpen] = useState(false);

  const { data: unread, refetch: refetchUnread } = useQuery({
    queryKey: ["notifications-unread"],
    queryFn: () => clientFetch<{ unread: number }>("/notifications/unread-count"),
    refetchInterval: 60_000,
  });

  const { data: list, refetch: refetchList } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => clientFetch<NotificationRead[]>("/notifications?limit=20"),
    enabled: open,
  });

  useHotspotSocket({
    wsUrl,
    onEvent: (e) => {
      if (e.event === "hotspot:new" || e.event === "notification") {
        refetchUnread(); // 角标实时 +1（FR-4.1）
        if (open) refetchList();
      }
    },
  });

  useEffect(() => {
    if (open) refetchList();
  }, [open, refetchList]);

  const markAll = async () => {
    await clientFetch("/notifications/read-all", { method: "POST" });
    refetchUnread();
    refetchList();
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="neon-btn relative rounded-lg p-2"
        aria-label="通知"
      >
        🔔
        {(unread?.unread ?? 0) > 0 && (
          <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--neon-pink)] px-1 text-[10px] font-bold text-white shadow-[0_0_10px_rgba(255,45,120,0.6)]">
            {unread!.unread > 99 ? "99+" : unread!.unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-12 z-40 w-96 rounded-xl border border-[var(--card-border)] bg-[rgba(6,10,22,0.95)] shadow-[0_0_32px_rgba(0,229,255,0.15)] backdrop-blur-xl">
          <div className="flex items-center justify-between border-b border-[var(--card-border)] px-4 py-3">
            <span className="text-sm font-semibold">通知中心</span>
            <button onClick={markAll} className="text-xs text-[var(--accent)] hover:underline">
              全部已读
            </button>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {list?.length === 0 && (
              <p className="p-6 text-center text-sm text-[var(--muted)]">暂无通知</p>
            )}
            {list?.map((n) => (
              <div
                key={n.id}
                className={`border-b border-[var(--card-border)] px-4 py-3 text-sm ${
                  n.is_read ? "opacity-50" : ""
                }`}
              >
                <div className="flex items-center gap-2">
                  {n.type === "alert" && (
                    <span className="rounded bg-red-500/15 px-1.5 py-0.5 text-xs text-red-400">
                      告警
                    </span>
                  )}
                  <span className="font-medium">{n.title}</span>
                </div>
                {n.content && (
                  <p className="mt-1 line-clamp-2 text-xs text-[var(--muted)]">{n.content}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
