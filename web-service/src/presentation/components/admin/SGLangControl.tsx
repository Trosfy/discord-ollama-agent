/**
 * SGLang Control Component
 *
 * Admin panel for starting/stopping the SGLang server.
 * Follows Single Responsibility - only handles SGLang control UI.
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Loader2, Play, Square, Server, RefreshCw, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

// ============================================================================
// Types
// ============================================================================

interface SGLangStatus {
  container: {
    status: "running" | "stopped" | "unknown" | "error";
    message: string;
  };
  internal_state: {
    status: "unknown" | "starting" | "running" | "stopping" | "stopped" | "error";
    message: string | null;
    started_at: string | null;
  };
  timestamp: string;
}

interface SGLangControlProps {
  /** API base URL */
  apiBaseUrl?: string;
  /** Custom className */
  className?: string;
  /** Polling interval in ms */
  pollInterval?: number;
}

// ============================================================================
// Component
// ============================================================================

export function SGLangControl({
  apiBaseUrl = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003",
  className,
  pollInterval = 5000,
}: SGLangControlProps) {
  const [status, setStatus] = useState<SGLangStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch status
  const fetchStatus = useCallback(async () => {
    try {
      setError(null);
      const response = await fetch(`${apiBaseUrl}/api/admin/sglang/status`, {
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch status: ${response.statusText}`);
      }

      const data = await response.json();
      setStatus(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch status";
      setError(message);
      console.error("[SGLangControl] Error:", err);
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl]);

  // Poll for status
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, pollInterval);
    return () => clearInterval(interval);
  }, [fetchStatus, pollInterval]);

  // Start SGLang
  const handleStart = async () => {
    setIsActionLoading(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/admin/sglang/start`, {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to start SGLang");
      }

      const data = await response.json();
      toast.success(data.message || "SGLang startup initiated");
      // Refresh status immediately
      await fetchStatus();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start SGLang";
      toast.error(message);
    } finally {
      setIsActionLoading(false);
    }
  };

  // Stop SGLang
  const handleStop = async () => {
    setIsActionLoading(true);
    try {
      const response = await fetch(`${apiBaseUrl}/api/admin/sglang/stop`, {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to stop SGLang");
      }

      toast.success("SGLang stopped successfully");
      await fetchStatus();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to stop SGLang";
      toast.error(message);
    } finally {
      setIsActionLoading(false);
    }
  };

  // Derive combined status
  const getDisplayStatus = () => {
    if (!status) return { label: "Unknown", color: "text-muted-foreground", bg: "bg-muted" };

    const containerRunning = status.container.status === "running";
    const internalState = status.internal_state.status;

    if (internalState === "starting") {
      return { label: "Starting", color: "text-[var(--status-warning)]", bg: "badge-warning" };
    }
    if (internalState === "stopping") {
      return { label: "Stopping", color: "text-[var(--status-warning)]", bg: "badge-warning" };
    }
    if (internalState === "error") {
      return { label: "Error", color: "text-[var(--status-error)]", bg: "badge-error" };
    }
    if (containerRunning) {
      return { label: "Running", color: "text-[var(--status-success)]", bg: "badge-success" };
    }
    return { label: "Stopped", color: "text-muted-foreground", bg: "bg-muted" };
  };

  const displayStatus = getDisplayStatus();
  const isRunning = status?.container.status === "running";
  const isStarting = status?.internal_state.status === "starting";
  const isStopping = status?.internal_state.status === "stopping";
  const canStart = !isRunning && !isStarting && !isActionLoading;
  const canStop = isRunning && !isStopping && !isActionLoading;

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            SGLang Server
          </CardTitle>

          <div className="flex items-center gap-3">
            <span className={cn("px-3 py-1 rounded-full text-sm font-medium", displayStatus.bg)}>
              {displayStatus.label}
            </span>
            <Button variant="ghost" size="icon" onClick={fetchStatus} title="Refresh">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Error message */}
        {(error || status?.internal_state.status === "error") && (
          <div className="flex items-start gap-2 p-3 rounded-lg badge-error">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <p className="text-sm">
              {error || status?.internal_state.message || "An error occurred"}
            </p>
          </div>
        )}

        {/* Status details */}
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Container:</span>
            <span className={cn(
              status?.container.status === "running" ? "text-[var(--status-success)]" : "text-muted-foreground"
            )}>
              {status?.container.status || "Unknown"}
            </span>
          </div>
          {status?.container.message && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Details:</span>
              <span className="text-right max-w-[200px] truncate">{status.container.message}</span>
            </div>
          )}
          {status?.internal_state.started_at && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Started:</span>
              <span>{new Date(status.internal_state.started_at).toLocaleTimeString()}</span>
            </div>
          )}
        </div>

        {/* Startup warning */}
        {isStarting && (
          <div className="flex items-center gap-2 p-3 rounded-lg badge-warning">
            <Loader2 className="h-4 w-4 animate-spin" />
            <p className="text-sm">
              Starting SGLang... This may take 5-10 minutes for MoE weight shuffling.
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-3 pt-2">
          <Button
            onClick={handleStart}
            disabled={!canStart}
            className="flex-1 gap-2"
          >
            {isStarting || (isActionLoading && !isRunning) ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Start
              </>
            )}
          </Button>

          <Button
            onClick={handleStop}
            disabled={!canStop}
            variant="destructive"
            className="flex-1 gap-2"
          >
            {isStopping || (isActionLoading && isRunning) ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Stopping...
              </>
            ) : (
              <>
                <Square className="h-4 w-4" />
                Stop
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
