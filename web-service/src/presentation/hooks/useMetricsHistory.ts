/**
 * Metrics History Hook
 *
 * Hook for querying historical time-series metrics from admin-service.
 * Supports multiple aggregation types and configurable granularity.
 */

"use client";

import { useState, useCallback } from "react";

// ============================================================================
// Types
// ============================================================================

export type MetricType = "vram" | "health" | "psi" | "queue";

export type AggregationType = "simple" | "max" | "min" | "sum" | "avg" | "p95" | "p99";

export type GranularitySeconds = 5 | 60 | 300 | 900 | 1800 | 3600;

export interface MetricsQueryParams {
  metricType: MetricType;
  field: string;
  startTime: string; // ISO 8601
  endTime: string; // ISO 8601
  granularity?: GranularitySeconds;
  aggregation?: AggregationType;
}

export interface MetricDataPoint {
  timestamp: string;
  value: number;
}

export interface MetricsSummary {
  count: number;
  min: number | null;
  max: number | null;
  avg: number | null;
  p95: number | null;
  p99: number | null;
}

export interface MetricsHistoryResponse {
  metric_type: string;
  field: string;
  start_time: string;
  end_time: string;
  granularity: number;
  aggregation: string;
  data_points: MetricDataPoint[];
  summary: MetricsSummary;
}

export interface MetricsSummaryResponse {
  metric_type: string;
  field: string;
  time_range: {
    start: string;
    end: string;
  };
  statistics: MetricsSummary;
}

// ============================================================================
// Hook
// ============================================================================

const ADMIN_API_URL = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003";

export function useMetricsHistory() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Query historical metrics with aggregation
   */
  const queryHistory = useCallback(
    async (params: MetricsQueryParams): Promise<MetricsHistoryResponse | null> => {
      try {
        setLoading(true);
        setError(null);

        const queryParams = new URLSearchParams({
          metric_type: params.metricType,
          field: params.field,
          start_time: params.startTime,
          end_time: params.endTime,
          granularity: (params.granularity || 5).toString(),
          aggregation: params.aggregation || "simple",
        });

        const response = await fetch(
          `${ADMIN_API_URL}/admin/metrics/history?${queryParams}`,
          {
            headers: {
              "Content-Type": "application/json",
            },
            credentials: "include",
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `HTTP ${response.status}: ${response.statusText}`
          );
        }

        const data: MetricsHistoryResponse = await response.json();
        return data;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to query metrics";
        setError(errorMessage);
        console.error("Metrics query error:", err);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  /**
   * Query summary statistics only (faster, no data points)
   */
  const querySummary = useCallback(
    async (
      metricType: MetricType,
      field: string,
      startTime: string,
      endTime: string
    ): Promise<MetricsSummaryResponse | null> => {
      try {
        setLoading(true);
        setError(null);

        const queryParams = new URLSearchParams({
          metric_type: metricType,
          field: field,
          start_time: startTime,
          end_time: endTime,
        });

        const response = await fetch(
          `${ADMIN_API_URL}/admin/metrics/summary?${queryParams}`,
          {
            headers: {
              "Content-Type": "application/json",
            },
            credentials: "include",
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(
            errorData.detail || `HTTP ${response.status}: ${response.statusText}`
          );
        }

        const data: MetricsSummaryResponse = await response.json();
        return data;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to query summary";
        setError(errorMessage);
        console.error("Summary query error:", err);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  /**
   * Helper: Query last N hours with specific aggregation
   */
  const queryLastHours = useCallback(
    async (
      hours: number,
      metricType: MetricType,
      field: string,
      granularity: GranularitySeconds = 60,
      aggregation: AggregationType = "avg"
    ): Promise<MetricsHistoryResponse | null> => {
      const endTime = new Date();
      const startTime = new Date(endTime.getTime() - hours * 60 * 60 * 1000);

      return queryHistory({
        metricType,
        field,
        startTime: startTime.toISOString(),
        endTime: endTime.toISOString(),
        granularity,
        aggregation,
      });
    },
    [queryHistory]
  );

  /**
   * Helper: Query last 24 hours with 1-minute averages
   */
  const queryLast24Hours = useCallback(
    async (
      metricType: MetricType,
      field: string
    ): Promise<MetricsHistoryResponse | null> => {
      return queryLastHours(24, metricType, field, 60, "avg");
    },
    [queryLastHours]
  );

  /**
   * Helper: Query last hour with raw 5-second data
   */
  const queryLastHour = useCallback(
    async (
      metricType: MetricType,
      field: string
    ): Promise<MetricsHistoryResponse | null> => {
      return queryLastHours(1, metricType, field, 5, "simple");
    },
    [queryLastHours]
  );

  return {
    loading,
    error,
    queryHistory,
    querySummary,
    queryLastHours,
    queryLast24Hours,
    queryLastHour,
  };
}

// ============================================================================
// Field Helper Constants
// ============================================================================

/**
 * Common metric field mappings for convenience
 */
export const METRIC_FIELDS = {
  vram: {
    used: "used_gb",
    total: "total_gb",
    available: "available_gb",
    percentage: "usage_percentage",
  },
  psi: {
    cpu: "cpu",
    memory: "memory",
    io: "io",
  },
  queue: {
    size: "size",
  },
} as const;

/**
 * Human-readable aggregation labels
 */
export const AGGREGATION_LABELS: Record<AggregationType, string> = {
  simple: "Raw Data",
  max: "Maximum",
  min: "Minimum",
  sum: "Sum",
  avg: "Average",
  p95: "95th Percentile",
  p99: "99th Percentile",
};

/**
 * Human-readable granularity labels
 */
export const GRANULARITY_LABELS: Record<GranularitySeconds, string> = {
  5: "5 seconds",
  60: "1 minute",
  300: "5 minutes",
  900: "15 minutes",
  1800: "30 minutes",
  3600: "1 hour",
};
