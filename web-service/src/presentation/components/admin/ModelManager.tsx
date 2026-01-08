/**
 * Model Manager Component
 *
 * Admin panel for loading/unloading AI models.
 * Follows Single Responsibility - only handles model management UI.
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Loader2, Play, Square, HardDrive, Cpu, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useVRAMMonitoring } from "@/hooks";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

// ============================================================================
// Types
// ============================================================================

export interface Model {
  name: string;
  size: string;
  quantization: string;
  loaded: boolean;
  vram_usage_gb?: number;
  family?: string;
  parameter_size?: string;
}

interface ModelManagerProps {
  /** API base URL */
  apiBaseUrl?: string;
  /** Custom className */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

export function ModelManager({
  apiBaseUrl = process.env.NEXT_PUBLIC_ADMIN_API_URL || "http://localhost:8003",
  className,
}: ModelManagerProps) {
  const [models, setModels] = useState<Model[]>([]);
  const [loadingModels, setLoadingModels] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { data: vramData, isConnected: vramConnected } = useVRAMMonitoring();

  // Fetch models list
  const fetchModels = useCallback(async () => {
    try {
      setError(null);
      const response = await fetch(`${apiBaseUrl}/api/admin/models`, {
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch models: ${response.statusText}`);
      }

      const data = await response.json();
      setModels(data.models || []);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load models";
      setError(message);
      console.error("[ModelManager] Error:", err);
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  // Load model
  const handleLoadModel = async (modelName: string) => {
    setLoadingModels((prev) => new Set(prev).add(modelName));

    try {
      const response = await fetch(
        `${apiBaseUrl}/api/admin/models/${encodeURIComponent(modelName)}/load`,
        {
          method: "POST",
          credentials: "include",
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `Failed to load model: ${response.statusText}`);
      }

      setModels((prev) =>
        prev.map((m) => (m.name === modelName ? { ...m, loaded: true } : m))
      );
      toast.success(`Model "${modelName}" loaded successfully`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load model";
      toast.error(message);
      console.error("[ModelManager] Load error:", err);
    } finally {
      setLoadingModels((prev) => {
        const next = new Set(prev);
        next.delete(modelName);
        return next;
      });
    }
  };

  // Unload model
  const handleUnloadModel = async (modelName: string) => {
    setLoadingModels((prev) => new Set(prev).add(modelName));

    try {
      const response = await fetch(
        `${apiBaseUrl}/api/admin/models/${encodeURIComponent(modelName)}/unload`,
        {
          method: "POST",
          credentials: "include",
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `Failed to unload model: ${response.statusText}`);
      }

      setModels((prev) =>
        prev.map((m) => (m.name === modelName ? { ...m, loaded: false } : m))
      );
      toast.success(`Model "${modelName}" unloaded successfully`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to unload model";
      toast.error(message);
      console.error("[ModelManager] Unload error:", err);
    } finally {
      setLoadingModels((prev) => {
        const next = new Set(prev);
        next.delete(modelName);
        return next;
      });
    }
  };

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

  // Error state
  if (error) {
    return (
      <Card className={className}>
        <CardContent className="flex flex-col items-center justify-center py-12 gap-4">
          <p className="text-destructive text-sm">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchModels}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            Model Manager
          </CardTitle>

          {/* VRAM Usage Bar */}
          {vramData && (
            <div className="flex items-center gap-3 text-sm">
              <HardDrive className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">
                {vramData.used_gb.toFixed(1)} / {vramData.total_gb.toFixed(1)} GB
              </span>
              <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full transition-all duration-300",
                    vramData.usage_percentage > 90
                      ? "bg-destructive"
                      : vramData.usage_percentage > 70
                      ? "bg-warning"
                      : "bg-success"
                  )}
                  style={{ width: `${Math.min(vramData.usage_percentage, 100)}%` }}
                />
              </div>
              {!vramConnected && (
                <span className="text-xs text-muted-foreground">(offline)</span>
              )}
            </div>
          )}

          <Button variant="ghost" size="icon" onClick={fetchModels} title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        {models.length === 0 ? (
          <p className="text-center text-muted-foreground py-8">
            No models available
          </p>
        ) : (
          <div className="space-y-3">
            {models.map((model) => {
              const isModelLoading = loadingModels.has(model.name);

              return (
                <div
                  key={model.name}
                  className={cn(
                    "flex items-center justify-between p-4 rounded-xl",
                    "bg-muted/50 border border-border",
                    "transition-colors hover:bg-muted"
                  )}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {/* Status indicator */}
                    <div
                      className={cn(
                        "h-3 w-3 rounded-full shrink-0",
                        model.loaded ? "bg-success" : "bg-muted-foreground"
                      )}
                    />

                    {/* Model info */}
                    <div className="min-w-0">
                      <p className="font-medium truncate">{model.name}</p>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        <span className="text-xs px-2 py-0.5 rounded bg-secondary text-secondary-foreground">
                          {model.size}
                        </span>
                        <span className="text-xs px-2 py-0.5 rounded border border-border text-muted-foreground">
                          {model.quantization}
                        </span>
                        {model.loaded && model.vram_usage_gb && (
                          <span className="text-xs text-muted-foreground">
                            {model.vram_usage_gb.toFixed(1)} GB VRAM
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Action button */}
                  <Button
                    size="sm"
                    variant={model.loaded ? "destructive" : "default"}
                    disabled={isModelLoading}
                    onClick={() =>
                      model.loaded
                        ? handleUnloadModel(model.name)
                        : handleLoadModel(model.name)
                    }
                    className="gap-2 min-w-[100px] shrink-0"
                  >
                    {isModelLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {model.loaded ? "Unloading..." : "Loading..."}
                      </>
                    ) : model.loaded ? (
                      <>
                        <Square className="h-4 w-4" />
                        Unload
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4" />
                        Load
                      </>
                    )}
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
