/**
 * useSSE Hook
 *
 * Generic Server-Sent Events hook for real-time data streaming.
 * Follows Open/Closed Principle - open for extension via generics.
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";

interface UseSSEOptions<T> {
  /** SSE endpoint URL */
  url: string;
  /** Callback when data is received */
  onMessage?: (data: T) => void;
  /** Callback on connection error */
  onError?: (error: Event) => void;
  /** Callback when connection opens */
  onOpen?: () => void;
  /** Enable/disable the connection */
  enabled?: boolean;
  /** Retry interval in ms after disconnect */
  retryInterval?: number;
  /** Include credentials in request */
  withCredentials?: boolean;
}

interface UseSSEReturn<T> {
  /** Latest data received */
  data: T | null;
  /** Connection status */
  isConnected: boolean;
  /** Last error event */
  error: Event | null;
  /** Manually trigger reconnection */
  reconnect: () => void;
  /** Manually disconnect */
  disconnect: () => void;
}

export function useSSE<T>({
  url,
  onMessage,
  onError,
  onOpen,
  enabled = true,
  retryInterval = 5000,
  withCredentials = true,
}: UseSSEOptions<T>): UseSSEReturn<T> {
  const [data, setData] = useState<T | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Event | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  // Store callbacks in refs to avoid reconnections
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onOpenRef = useRef(onOpen);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
    onOpenRef.current = onOpen;
  }, [onMessage, onError, onOpen]);

  const disconnect = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!enabled || !mountedRef.current) return;

    // Clean up existing connection
    disconnect();

    try {
      const eventSource = new EventSource(url, { withCredentials });
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        setError(null);
        onOpenRef.current?.();
      };

      eventSource.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const parsedData = JSON.parse(event.data) as T;
          setData(parsedData);
          onMessageRef.current?.(parsedData);
        } catch (e) {
          console.error("[useSSE] Failed to parse data:", e);
        }
      };

      eventSource.onerror = (event) => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        setError(event);
        onErrorRef.current?.(event);
        eventSource.close();

        // Schedule retry
        retryTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) {
            connect();
          }
        }, retryInterval);
      };
    } catch (e) {
      console.error("[useSSE] Failed to create EventSource:", e);
    }
  }, [url, enabled, retryInterval, withCredentials, disconnect]);

  const reconnect = useCallback(() => {
    disconnect();
    connect();
  }, [disconnect, connect]);

  // Connect on mount, cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    data,
    isConnected,
    error,
    reconnect,
    disconnect,
  };
}
