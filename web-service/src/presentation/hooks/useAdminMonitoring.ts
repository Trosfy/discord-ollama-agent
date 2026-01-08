/**
 * Admin Monitoring Hooks
 *
 * Specialized SSE hooks for admin dashboard real-time data.
 * Follows Dependency Inversion - depends on useSSE abstraction.
 */

"use client";

import { useCallback, useEffect, useRef } from "react";
import { useSSE } from "./useSSE";
import { useAuth } from "./useAuth";
import { isTokenExpired } from "@/infrastructure/api/FetchClient";

// ============================================================================
// Types - Match backend SSE data structures
// ============================================================================

export interface LoadedModel {
  name: string;
  size_gb: number;
  backend: string;  // "sglang" | "ollama"
  is_loaded: boolean;  // True if model is currently in memory
  can_toggle: boolean;  // True if model can be loaded/unloaded via API
  family?: string;
}

export interface VRAMStats {
  total_gb: number;
  used_gb: number;
  available_gb: number;
  usage_percentage: number;
  loaded_models: LoadedModel[];
}

export interface ServiceHealth {
  dynamodb: "healthy" | "unhealthy" | "unknown";
  ollama: "healthy" | "unhealthy" | "unknown";
  sglang?: "healthy" | "unhealthy" | "stopped" | "starting" | "unknown";
  fastapi?: "healthy" | "unhealthy" | "unknown";
  discord_bot?: "healthy" | "unhealthy" | "unknown";
}

export interface PSIMetrics {
  cpu: number;
  memory: number;
  io: number;
}

export interface GPUMetrics {
  temperature_c: number;
  power_draw_w: number;
  utilization_pct: number;
}

export interface MonitoringData {
  vram: VRAMStats;
  services: ServiceHealth;
  queue_size: number;
  maintenance_mode: boolean;
  psi?: PSIMetrics;
  gpu?: GPUMetrics;
  cpu_utilization?: number;
  timestamp: string;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook for combined admin monitoring data stream
 * Provides VRAM, services, queue, and PSI data in one stream
 */
export function useAdminMonitoring(enabled = true) {
  const baseUrl = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003";
  const { accessToken, refreshAccessToken } = useAuth();
  const isRefreshingRef = useRef(false);

  // Construct URL with token query parameter for SSE authentication
  const url = accessToken
    ? `${baseUrl}/admin/monitoring/stream?token=${encodeURIComponent(accessToken)}`
    : `${baseUrl}/admin/monitoring/stream`;

  // Handle SSE errors - check if token expired and refresh
  const handleError = useCallback(async () => {
    // Prevent concurrent refresh attempts
    if (isRefreshingRef.current) return;

    // Check if token is expired
    if (isTokenExpired(accessToken)) {
      isRefreshingRef.current = true;
      console.log("[useAdminMonitoring] Token expired, attempting refresh...");

      try {
        const newToken = await refreshAccessToken();
        if (newToken) {
          console.log("[useAdminMonitoring] Token refreshed successfully");
        } else {
          console.warn("[useAdminMonitoring] Token refresh failed");
        }
      } finally {
        isRefreshingRef.current = false;
      }
    }
  }, [accessToken, refreshAccessToken]);

  const sse = useSSE<MonitoringData>({
    url,
    enabled: enabled && !!accessToken && !isTokenExpired(accessToken),
    retryInterval: 5000,
    withCredentials: false, // Token is in URL, not cookies
    onError: handleError,
  });

  // Also check token expiry periodically while connected
  useEffect(() => {
    if (!enabled || !accessToken) return;

    const checkInterval = setInterval(async () => {
      if (isTokenExpired(accessToken) && !isRefreshingRef.current) {
        isRefreshingRef.current = true;
        console.log("[useAdminMonitoring] Proactive token refresh...");

        try {
          const newToken = await refreshAccessToken();
          if (newToken) {
            // SSE will reconnect with new token on next retry
            sse.reconnect();
          }
        } finally {
          isRefreshingRef.current = false;
        }
      }
    }, 60000); // Check every minute

    return () => clearInterval(checkInterval);
  }, [enabled, accessToken, refreshAccessToken, sse]);

  return sse;
}

/**
 * Hook for VRAM-specific monitoring
 * Use when you only need VRAM data (lighter payload)
 */
export function useVRAMMonitoring(enabled = true) {
  const baseUrl = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003";
  const { accessToken, refreshAccessToken } = useAuth();
  const isRefreshingRef = useRef(false);

  const url = accessToken
    ? `${baseUrl}/admin/vram/stream?token=${encodeURIComponent(accessToken)}`
    : `${baseUrl}/admin/vram/stream`;

  const handleError = useCallback(async () => {
    if (isRefreshingRef.current) return;
    if (isTokenExpired(accessToken)) {
      isRefreshingRef.current = true;
      try {
        await refreshAccessToken();
      } finally {
        isRefreshingRef.current = false;
      }
    }
  }, [accessToken, refreshAccessToken]);

  return useSSE<VRAMStats>({
    url,
    enabled: enabled && !!accessToken && !isTokenExpired(accessToken),
    retryInterval: 5000,
    withCredentials: false,
    onError: handleError,
  });
}

/**
 * Hook for service health monitoring
 * Use when you only need service status
 */
export function useHealthMonitoring(enabled = true) {
  const baseUrl = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003";
  const { accessToken, refreshAccessToken } = useAuth();
  const isRefreshingRef = useRef(false);

  const url = accessToken
    ? `${baseUrl}/admin/health/stream?token=${encodeURIComponent(accessToken)}`
    : `${baseUrl}/admin/health/stream`;

  const handleError = useCallback(async () => {
    if (isRefreshingRef.current) return;
    if (isTokenExpired(accessToken)) {
      isRefreshingRef.current = true;
      try {
        await refreshAccessToken();
      } finally {
        isRefreshingRef.current = false;
      }
    }
  }, [accessToken, refreshAccessToken]);

  return useSSE<ServiceHealth>({
    url,
    enabled: enabled && !!accessToken && !isTokenExpired(accessToken),
    retryInterval: 5000,
    withCredentials: false,
    onError: handleError,
  });
}
