"use client";

import { Cpu, Info } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useMonitoring } from "@/contexts/MonitoringContext";
import { useModelManagement } from "@/hooks/useModelManagement";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { API_CONFIG } from "@/config/api.config";

interface Model {
  name: string;
  backend: string;
  is_loaded: boolean;
  can_toggle: boolean;
  size_gb?: number;
}

export function DashboardModelsQuick() {
  const { data } = useMonitoring();
  const { loadModel, unloadModel } = useModelManagement();
  const [showDialog, setShowDialog] = useState(false);
  const [transitioning, setTransitioning] = useState<Set<string>>(new Set());
  const [models, setModels] = useState<Model[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);

  const queueSize = data?.queue_size || 0;

  // Fetch all available models from /admin/models/list
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const token = localStorage.getItem("trollama_auth_token");
        if (!token) {
          console.warn("No auth token - skipping model fetch");
          setIsLoadingModels(false);
          return;
        }

        const response = await fetch(API_CONFIG.ENDPOINTS.ADMIN.MODELS.LIST, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          // Transform API response to match our Model interface
          const transformedModels = (data.models || []).map((m: any) => ({
            name: m.name,
            backend: m.backend?.type || "ollama",
            is_loaded: m.is_loaded || false,
            can_toggle: m.api_managed ?? true, // SSOT from troise-ai
            size_gb: m.vram_size_gb,
          }));
          setModels(transformedModels);
        }
      } catch (error) {
        console.error("Failed to fetch available models:", error);
      } finally {
        setIsLoadingModels(false);
      }
    };

    fetchModels();
    // Refresh every 10 seconds
    const interval = setInterval(fetchModels, 10000);
    return () => clearInterval(interval);
  }, []);

  // Group models by backend and sort alphabetically
  const sglangModels = models
    .filter((m) => m.backend === "sglang")
    .sort((a, b) => a.name.localeCompare(b.name));
  const ollamaModels = models
    .filter((m) => m.backend === "ollama")
    .sort((a, b) => a.name.localeCompare(b.name));

  const handleModelToggle = async (
    modelName: string,
    shouldLoad: boolean,
    canToggle: boolean
  ) => {
    // Only api_managed models can be toggled
    if (!canToggle) {
      return;
    }

    // Mark as transitioning
    setTransitioning((prev) => new Set(prev).add(modelName));

    // Handle Ollama model toggle
    try {
      if (shouldLoad) {
        await loadModel(modelName);
        toast.success(`Prewarming ${modelName} for 10 minutes`);
      } else {
        await unloadModel(modelName);
        toast.success(`Unloaded ${modelName}`);
      }
    } catch (err) {
      toast.error(
        `Failed to ${shouldLoad ? "load" : "unload"} ${modelName}`
      );
    } finally {
      // Remove from transitioning
      setTransitioning((prev) => {
        const next = new Set(prev);
        next.delete(modelName);
        return next;
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5" />
            Models & Queue
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0"
            onClick={() => setShowDialog(true)}
          >
            <Info className="h-4 w-4" />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* Quick stats */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-muted-foreground mb-1">
                Total Models
              </div>
              <div className="text-2xl font-semibold">{models.length}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">
                Queue Size
              </div>
              <div className="text-2xl font-semibold">{queueSize}</div>
            </div>
          </div>

          {/* SGLang models section (read-only) */}
          {sglangModels.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                SGLang (Serving)
              </div>
              {sglangModels.map((model) => (
                <div
                  key={model.name}
                  className="flex items-center justify-between"
                >
                  <span className="text-sm truncate flex-1">{model.name}</span>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="1"
                    value={1} // Always ON
                    disabled={true} // Cannot toggle
                    className="w-10 h-2 bg-secondary rounded-lg appearance-none cursor-not-allowed transition-colors ml-2"
                    style={{ accentColor: "var(--muted-foreground)" }} // Muted to indicate disabled
                  />
                </div>
              ))}
            </div>
          )}

          {/* Ollama models section (interactive) */}
          {ollamaModels.length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Ollama (Prewarm 10m)
              </div>
              {ollamaModels.map((model) => {
                const isTransitioning = transitioning.has(model.name);
                const isLoaded = model.is_loaded;

                return (
                  <div
                    key={model.name}
                    className="flex items-center justify-between gap-2"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-sm truncate">{model.name}</span>
                    </div>
                    <div className="text-xs font-mono shrink-0">
                      {isTransitioning && (
                        <span className="text-amber-500 animate-pulse">
                          {isLoaded ? "Unloading..." : "Prewarming..."}
                        </span>
                      )}
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="1"
                      value={isLoaded ? 1 : 0}
                      disabled={!model.can_toggle || isTransitioning}
                      onChange={(e) =>
                        handleModelToggle(
                          model.name,
                          parseInt(e.target.value) === 1,
                          model.can_toggle
                        )
                      }
                      className={`w-10 h-2 bg-secondary rounded-lg appearance-none transition-colors shrink-0 ${
                        model.can_toggle && !isTransitioning
                          ? "cursor-pointer"
                          : isTransitioning
                          ? "cursor-wait opacity-50"
                          : "cursor-not-allowed opacity-50"
                      }`}
                      style={{
                        accentColor: isLoaded ? "var(--primary)" : "var(--muted-foreground)"
                      }}
                    />
                  </div>
                );
              })}
            </div>
          )}

          {models.length === 0 && (
            <div className="text-sm text-muted-foreground text-center py-4">
              No models available
            </div>
          )}
        </div>
      </CardContent>

      {/* Full Model Management Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Cpu className="h-5 w-5" />
              Model Management
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6">
            {/* Queue Status */}
            <div className="p-4 bg-secondary/50 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">Queue Size</div>
                  <div className="text-xs text-muted-foreground">
                    Pending requests
                  </div>
                </div>
                <div className="text-3xl font-semibold">{queueSize}</div>
              </div>
            </div>

            {/* Model Summary */}
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-secondary/30 rounded-lg">
                <div className="text-sm text-muted-foreground mb-1">
                  Total Models
                </div>
                <div className="text-2xl font-semibold">{models.length}</div>
              </div>
              <div className="p-4 bg-secondary/30 rounded-lg">
                <div className="text-sm text-muted-foreground mb-1">
                  Loaded Models
                </div>
                <div className="text-2xl font-semibold">
                  {models.filter((m) => m.is_loaded).length}
                </div>
              </div>
            </div>

            {/* SGLang Models Section (Read-only) */}
            {sglangModels.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">
                    SGLang Models (Always Serving)
                  </h3>
                  <span className="text-xs text-muted-foreground">
                    {sglangModels.length} model{sglangModels.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div className="space-y-2">
                  {sglangModels.map((model) => (
                    <div
                      key={model.name}
                      className="flex items-center justify-between p-3 bg-secondary/20 rounded-lg"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm truncate">
                          {model.name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Backend: {model.backend}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs font-mono text-green-500">
                          LOADED
                        </span>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="1"
                          value={1}
                          disabled={true}
                          className="w-10 h-2 bg-secondary rounded-lg appearance-none cursor-not-allowed"
                          style={{ accentColor: "var(--muted-foreground)" }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Ollama Models Section (Interactive) */}
            {ollamaModels.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">
                    Ollama Models (10-Minute Prewarm)
                  </h3>
                  <span className="text-xs text-muted-foreground">
                    {ollamaModels.length} model{ollamaModels.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div className="space-y-2">
                  {ollamaModels.map((model) => {
                    const isTransitioning = transitioning.has(model.name);
                    const isLoaded = model.is_loaded;

                    return (
                      <div
                        key={model.name}
                        className="flex items-center justify-between p-3 bg-secondary/20 rounded-lg"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-sm truncate">
                            {model.name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Backend: {model.backend}
                            {!model.can_toggle && " (Toggle disabled)"}
                          </div>
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          {isTransitioning && (
                            <span className="text-xs font-mono text-amber-500 animate-pulse">
                              {isLoaded ? "Unloading..." : "Prewarming..."}
                            </span>
                          )}
                          {!isTransitioning && (
                            <span
                              className={`text-xs font-mono ${
                                isLoaded ? "text-green-500" : "text-muted-foreground"
                              }`}
                            >
                              {isLoaded ? "LOADED" : "UNLOADED"}
                            </span>
                          )}
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="1"
                            value={isLoaded ? 1 : 0}
                            disabled={!model.can_toggle || isTransitioning}
                            onChange={(e) =>
                              handleModelToggle(
                                model.name,
                                parseInt(e.target.value) === 1,
                                model.can_toggle
                              )
                            }
                            className={`w-10 h-2 bg-secondary rounded-lg appearance-none transition-colors ${
                              model.can_toggle && !isTransitioning
                                ? "cursor-pointer"
                                : isTransitioning
                                ? "cursor-wait opacity-50"
                                : "cursor-not-allowed opacity-50"
                            }`}
                            style={{
                              accentColor: isLoaded
                                ? "var(--primary)"
                                : "var(--muted-foreground)",
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {models.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <Cpu className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p className="text-sm">No models available</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
