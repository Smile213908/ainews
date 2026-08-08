/** 全量立即检查入口（FR-7.3）：仪表盘统一触发按钮。
 *
 * - 点击 POST /check-hotspots，202 后轮询进度；409 说明已有检查在跑，直接接管轮询；
 * - 挂载时先查一次状态：若 cron/其他入口已在检查，如实反映并跟踪进度；
 * - 完成后刷新热点流、关键词计数与 RSC 统计。
 */

"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { clientFetch } from "@/lib/api";

type CheckStatus = {
  running: boolean;
  total_keywords: number;
  done_keywords: number;
  current_keyword: string | null;
  hotspots_created: number;
};

const POLL_MS = 3000;

export default function CheckTrigger() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [status, setStatus] = useState<CheckStatus | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  };

  const finish = useCallback(
    (st: CheckStatus) => {
      stopPolling();
      setStatus(st);
      setNotice(`完成，新增 ${st.hotspots_created} 条热点`);
      queryClient.invalidateQueries({ queryKey: ["hotspots"] });
      queryClient.invalidateQueries({ queryKey: ["keywords"] });
      router.refresh(); // 刷新 RSC 统计卡片
    },
    [queryClient, router]
  );

  const startPolling = useCallback(() => {
    if (timer.current) return;
    timer.current = setInterval(async () => {
      try {
        const st = await clientFetch<CheckStatus>("/check-hotspots/status");
        if (st.running) {
          setStatus(st);
        } else {
          finish(st);
        }
      } catch {
        /* 单次轮询失败忽略，下一轮重试 */
      }
    }, POLL_MS);
  }, [finish]);

  // 挂载时接管已在进行的检查（cron 触发或从关键词页触发）
  useEffect(() => {
    clientFetch<CheckStatus>("/check-hotspots/status")
      .then((st) => {
        setStatus(st);
        if (st.running) startPolling();
      })
      .catch(() => {});
    return stopPolling;
  }, [startPolling]);

  const trigger = async () => {
    setNotice(null);
    try {
      await clientFetch("/check-hotspots", { method: "POST" });
      const st = await clientFetch<CheckStatus>("/check-hotspots/status");
      setStatus(st);
      startPolling();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("返回 409")) {
        // 已有检查进行中：不报错，直接跟踪进度
        const st = await clientFetch<CheckStatus>("/check-hotspots/status").catch(
          () => null
        );
        if (st) setStatus(st);
        startPolling();
      } else {
        setNotice("触发失败，稍后再试");
      }
    }
  };

  const running = status?.running ?? false;

  return (
    <div className="flex items-center gap-3 text-xs">
      {running && status && (
        <span className="text-[var(--accent)]">
          检查中 {status.done_keywords}/{status.total_keywords}
          {status.current_keyword ? ` · ${status.current_keyword}` : ""}
        </span>
      )}
      {!running && notice && <span className="text-[var(--muted)]">{notice}</span>}
      <button
        onClick={trigger}
        disabled={running}
        className="rounded-lg border border-[var(--accent)]/40 px-4 py-2 text-sm font-medium text-[var(--accent)] hover:bg-[var(--accent)]/10 disabled:opacity-40"
      >
        {running ? "检查中…" : "立即检查"}
      </button>
    </div>
  );
}
