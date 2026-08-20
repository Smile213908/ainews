/** 全量立即检查入口（FR-7.3）：仪表盘统一触发按钮。
 *
 * - 点击后立即弹出进度弹窗，POST /check-hotspots，202 后轮询进度；
 *   409 说明已有检查在跑，直接接管轮询；
 * - 挂载时先查一次状态：若 cron/其他入口已在检查，自动打开弹窗接管跟踪；
 * - 完成后刷新热点流、关键词计数与 RSC 统计，弹窗保留总结供点击查看。
 */

"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import CheckProgressModal, { CheckStatus } from "@/components/check-progress-modal";
import { clientFetch } from "@/lib/api";

const POLL_MS = 3000;

export default function CheckTrigger() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [status, setStatus] = useState<CheckStatus | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
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
        if (st.running) {
          setModalOpen(true);
          startPolling();
        }
      })
      .catch(() => {});
    return stopPolling;
  }, [startPolling]);

  const trigger = async () => {
    setModalOpen(true); // 立即渲染弹窗，不等待后端响应
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
        setModalOpen(false);
        setStatus(null);
      }
    }
  };

  const running = status?.running ?? false;

  return (
    <div className="flex items-center gap-3 text-xs">
      {running && !modalOpen && (
        <button
          onClick={() => setModalOpen(true)}
          className="text-[var(--accent)] hover:underline"
        >
          检查中 {status?.done_keywords}/{status?.total_keywords} · 查看进度
        </button>
      )}
      {!running && status && !modalOpen && (
        <button
          onClick={() => setModalOpen(true)}
          className="text-[var(--muted)] hover:text-[var(--foreground)] hover:underline"
        >
          上轮新增 {status.hotspots_created} 条 · 查看报告
        </button>
      )}
      <button
        onClick={trigger}
        disabled={running}
        className="neon-btn rounded-lg px-4 py-2 text-sm font-medium"
      >
        {running ? "◉ 检查中…" : "⚡ 立即检查"}
      </button>
      {modalOpen && (
        <CheckProgressModal status={status} onClose={() => setModalOpen(false)} />
      )}
    </div>
  );
}
