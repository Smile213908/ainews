/**
 * WebSocket 实时推送 hook（技术选型 §3.5 / FR-2.6）。
 *
 * - 指数退避重连（1s→2s→…→30s 封顶）；
 * - 重连成功后触发一次全量刷新（onReconnect）；
 * - 页面隐藏时暂停心跳（浏览器自动挂起，此处监听可见性主动重连）。
 */

"use client";

import { useEffect, useRef } from "react";

export type WsEvent = {
  event: "hotspot:new" | "notification" | "task:update";
  data: Record<string, unknown>;
};

export function useHotspotSocket(opts: {
  wsUrl: string;
  keywords?: string[];
  onEvent: (e: WsEvent) => void;
  onReconnect?: () => void;
}) {
  const { wsUrl, keywords, onEvent, onReconnect } = opts;
  const attemptsRef = useRef(0);
  const callbacksRef = useRef({ onEvent, onReconnect });
  callbacksRef.current = { onEvent, onReconnect };

  useEffect(() => {
    if (!wsUrl) return;
    let ws: WebSocket | null = null;
    let closedByUs = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      const params = new URLSearchParams();
      if (keywords?.length) params.set("keywords", keywords.join(","));
      const sep = wsUrl.includes("?") ? "&" : "?";
      ws = new WebSocket(`${wsUrl}${sep}${params.toString()}`);

      ws.onopen = () => {
        const wasReconnect = attemptsRef.current > 0;
        attemptsRef.current = 0;
        if (wasReconnect) callbacksRef.current.onReconnect?.();
      };
      ws.onmessage = (msg) => {
        try {
          callbacksRef.current.onEvent(JSON.parse(msg.data) as WsEvent);
        } catch {
          /* 忽略非 JSON 帧 */
        }
      };
      ws.onclose = () => {
        if (closedByUs) return;
        const delay = Math.min(1000 * 2 ** attemptsRef.current, 30_000);
        attemptsRef.current += 1;
        timer = setTimeout(connect, delay);
      };
    };

    connect();
    const onVisible = () => {
      if (document.visibilityState === "visible" && ws?.readyState === WebSocket.CLOSED) {
        connect();
      }
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      closedByUs = true;
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
      ws?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsUrl, keywords?.join(",")]);
}
