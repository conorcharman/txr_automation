import { useEffect, useRef, useState, useCallback } from "react";
import type { WsMessage } from "@/types";

type WsStatus = "connecting" | "connected" | "disconnected" | "error";

const TERMINAL_STATUSES = new Set(["success", "failed", "cancelled"]);

interface UseWebSocketOptions {
  onMessage: (msg: WsMessage) => void;
  onStatusChange?: (status: WsStatus) => void;
  enabled?: boolean;
  maxRetries?: number;
}

interface UseWebSocketReturn {
  status: WsStatus;
  disconnect: () => void;
}

export function useWebSocket(
  url: string,
  options: UseWebSocketOptions,
): UseWebSocketReturn {
  const { onMessage, onStatusChange, enabled = true, maxRetries = 5 } = options;

  const [status, setStatus] = useState<WsStatus>("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stoppedRef = useRef(false);

  // Keep latest callbacks in refs to avoid stale closures
  const onMessageRef = useRef(onMessage);
  const onStatusChangeRef = useRef(onStatusChange);
  onMessageRef.current = onMessage;
  onStatusChangeRef.current = onStatusChange;

  const updateStatus = useCallback((next: WsStatus) => {
    setStatus(next);
    onStatusChangeRef.current?.(next);
  }, []);

  const connect = useCallback(() => {
    if (stoppedRef.current) return;

    updateStatus("connecting");

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      retriesRef.current = 0;
      updateStatus("connected");
    };

    ws.onmessage = (event: MessageEvent) => {
      let msg: WsMessage;
      try {
        const parsed: unknown = JSON.parse(event.data as string);
        if (
          parsed !== null &&
          typeof parsed === "object" &&
          "type" in parsed &&
          "data" in parsed
        ) {
          const p = parsed as Record<string, unknown>;
          if (
            (p["type"] === "log" || p["type"] === "status") &&
            typeof p["data"] === "string"
          ) {
            msg = { type: p["type"], data: p["data"] };
          } else if (p["type"] === "progress" && typeof p["data"] === "number") {
            msg = { type: "progress", data: p["data"] };
          } else if (p["type"] === "progress" && typeof p["data"] === "string") {
            const maybeProgress = Number.parseInt(p["data"], 10);
            if (Number.isFinite(maybeProgress)) {
              msg = { type: "progress", data: maybeProgress };
            } else {
              msg = { type: "log", data: event.data as string };
            }
          } else {
            msg = { type: "log", data: event.data as string };
          }
        } else {
          msg = { type: "log", data: event.data as string };
        }
      } catch {
        msg = { type: "log", data: event.data as string };
      }

      onMessageRef.current(msg);

      // Stop reconnecting on terminal status messages
      if (msg.type === "status" && typeof msg.data === "string" && TERMINAL_STATUSES.has(msg.data)) {
        stoppedRef.current = true;
      }
    };

    ws.onerror = () => {
      updateStatus("error");
    };

    ws.onclose = () => {
      if (stoppedRef.current) {
        updateStatus("disconnected");
        return;
      }

      const attempt = retriesRef.current;
      if (attempt >= maxRetries) {
        updateStatus("disconnected");
        return;
      }

      const delayMs = Math.pow(2, attempt) * 1000; // 1s, 2s, 4s, 8s, 16s
      retriesRef.current = attempt + 1;
      updateStatus("connecting");

      retryTimerRef.current = setTimeout(() => {
        connect();
      }, delayMs);
    };
  }, [url, maxRetries, updateStatus]);

  const disconnect = useCallback(() => {
    stoppedRef.current = true;
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => {
    if (!enabled) return;

    stoppedRef.current = false;
    retriesRef.current = 0;
    connect();

    return () => {
      stoppedRef.current = true;
      if (retryTimerRef.current !== null) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [url, enabled, connect]);

  return { status, disconnect };
}
