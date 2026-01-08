/**
 * Presentation Hooks Barrel Export
 *
 * Centralized exports for all presentation layer hooks.
 * Follows Interface Segregation - consumers import only what they need.
 */

// Chat Hooks
export { useChatStream } from "./useChatStream";
export { useAuth } from "./useAuth";
export { useFileAttachments } from "./useFileAttachments";

// SSE Hooks (for admin real-time data)
export { useSSE } from "./useSSE";
export {
  useAdminMonitoring,
  useVRAMMonitoring,
  useHealthMonitoring,
} from "./useAdminMonitoring";
export type {
  VRAMStats,
  ServiceHealth,
  MonitoringData,
} from "./useAdminMonitoring";

// Historical Metrics Hooks
export { useMetricsHistory } from "./useMetricsHistory";
export type {
  MetricType,
  AggregationType,
  GranularitySeconds,
  MetricsQueryParams,
  MetricDataPoint,
  MetricsHistoryResponse,
  MetricsSummaryResponse,
} from "./useMetricsHistory";
