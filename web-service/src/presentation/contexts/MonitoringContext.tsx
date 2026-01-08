"use client";

import { createContext, useContext, ReactNode } from "react";
import { useAdminMonitoring } from "@/hooks/useAdminMonitoring";
import type { MonitoringData } from "@/hooks/useAdminMonitoring";

interface MonitoringContextValue {
  data: MonitoringData | null;
  isConnected: boolean;
  error: Event | null;
}

const MonitoringContext = createContext<MonitoringContextValue | undefined>(
  undefined
);

interface MonitoringProviderProps {
  children: ReactNode;
}

/**
 * Monitoring Context Provider
 *
 * Maintains a single SSE connection for all admin dashboard components.
 * Prevents duplicate connections and race conditions.
 */
export function MonitoringProvider({ children }: MonitoringProviderProps) {
  const { data, isConnected, error } = useAdminMonitoring();

  return (
    <MonitoringContext.Provider value={{ data, isConnected, error }}>
      {children}
    </MonitoringContext.Provider>
  );
}

/**
 * Hook to access shared monitoring data
 *
 * Must be used within MonitoringProvider.
 * Returns the same data as useAdminMonitoring but from a shared connection.
 */
export function useMonitoring() {
  const context = useContext(MonitoringContext);
  if (context === undefined) {
    throw new Error("useMonitoring must be used within MonitoringProvider");
  }
  return context;
}
