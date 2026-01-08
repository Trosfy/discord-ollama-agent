"use client";

import { useSettingsStore } from "@/stores/settingsStore";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Sparkles, Brain, Bot, ChevronDown, Cpu } from "lucide-react";
import { useMemo, useEffect, useState } from "react";
import { useMonitoring } from "@/contexts/MonitoringContext";
import { cn } from "@/lib/utils";
import { API_CONFIG } from "@/config/api.config";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * Chat Settings Component
 *
 * Configure chat behavior: temperature, thinking mode, model selection, display options.
 */
export function ChatSettings() {
  const {
    temperature,
    thinkingEnabled,
    selectedModelId,
    showTimestamps,
    compactMode,
    setTemperature,
    setThinkingEnabled,
    setSelectedModelId,
    setShowTimestamps,
    setCompactMode,
  } = useSettingsStore();

  // Fetch all available models from API (Ollama + SGLang)
  const [availableModels, setAvailableModels] = useState<any[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);

  // Get real-time loaded model status from SSE
  const { data } = useMonitoring();
  const loadedModels = data?.vram?.loaded_models || [];

  // Fetch all available models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        // Get auth token from localStorage
        const token = localStorage.getItem("trollama_auth_token");
        if (!token) {
          console.warn("No auth token - skipping model fetch");
          setIsLoadingModels(false);
          return;
        }

        const response = await fetch(API_CONFIG.ENDPOINTS.ADMIN.MODELS.LIST, {
          headers: {
            "Authorization": `Bearer ${token}`,
          },
        });
        if (response.ok) {
          const data = await response.json();
          setAvailableModels(data.models || []);
        }
      } catch (error) {
        console.error("Failed to fetch available models:", error);
      } finally {
        setIsLoadingModels(false);
      }
    };

    fetchModels();
  }, []);

  // Transform model list to dropdown format
  const models = useMemo(() => {
    // Always include trollama router option at the top
    const trollamaOption = {
      id: "trollama",
      name: "trollama",
      description: "",
      icon: "trollama" as const,
      status: "" // No status indicator for router
    };

    if (availableModels.length === 0) {
      // Fallback: Just show Trollama option
      return [trollamaOption];
    }

    // Transform all available models with real-time loaded status
    const modelList = availableModels.map(model => {
      const shortName = model.name.split('/').pop() || model.name;

      // Check if model is currently loaded (from SSE)
      const isLoaded = loadedModels.some(loaded => loaded.name === model.name);
      const statusColor = isLoaded ? "bg-green-500" : "bg-gray-400";

      return {
        id: model.name,
        name: shortName,
        backend: model.backend?.type || "ollama",
        description: "",
        status: statusColor,
        icon: "default" as const
      };
    }).sort((a, b) => a.name.localeCompare(b.name)); // Sort alphabetically

    // Prepend trollama option (stays at top)
    return [trollamaOption, ...modelList];
  }, [availableModels, loadedModels]);

  return (
    <div className="space-y-6">
      {/* Generation Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            Generation Settings
          </CardTitle>
          <CardDescription>
            Control how the AI generates responses
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Temperature */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label htmlFor="temperature" className="text-base">
                Temperature
              </Label>
              <span className="text-sm text-muted-foreground font-mono">
                {temperature.toFixed(1)}
              </span>
            </div>
            <input
              id="temperature"
              type="range"
              min="0"
              max="2"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
            />
            <p className="text-sm text-muted-foreground">
              Lower values: focused and consistent responses<br />
              Higher values: creative and varied responses
            </p>
          </div>

          {/* Thinking/Reasoning Toggle */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain className="h-4 w-4" />
                <Label htmlFor="thinking" className="text-base">
                  Thinking Mode
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="thinking"
                  type="checkbox"
                  checked={thinkingEnabled}
                  onChange={(e) => setThinkingEnabled(e.target.checked)}
                  className="w-4 h-4 rounded accent-primary cursor-pointer"
                />
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              Extended reasoning for complex queries (slower responses)
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Display Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            Display Preferences
          </CardTitle>
          <CardDescription>
            Customize how chat messages are displayed
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Show Timestamps */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="timestamps" className="text-base">
                Show Timestamps
              </Label>
              <p className="text-sm text-muted-foreground">
                Display message timestamps in chat
              </p>
            </div>
            <input
              id="timestamps"
              type="checkbox"
              checked={showTimestamps}
              onChange={(e) => setShowTimestamps(e.target.checked)}
              className="w-4 h-4 rounded accent-primary cursor-pointer"
            />
          </div>

          {/* Compact Mode */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="compact" className="text-base">
                Compact Mode
              </Label>
              <p className="text-sm text-muted-foreground">
                Reduce spacing between messages
              </p>
            </div>
            <input
              id="compact"
              type="checkbox"
              checked={compactMode}
              onChange={(e) => setCompactMode(e.target.checked)}
              className="w-4 h-4 rounded accent-primary cursor-pointer"
            />
          </div>

          {/* Default Model Selection */}
          <div className="space-y-3">
            <Label htmlFor="model" className="text-base">
              Default Model
            </Label>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="flex items-center justify-between w-full px-3 py-2 text-sm rounded-md border border-input bg-background hover:bg-accent hover:text-accent-foreground"
                >
                  <div className="flex items-center gap-2">
                    {models.find(m => m.id === selectedModelId)?.icon === "trollama" ? (
                      <img
                        src="/trollama-badge-no-bg.svg"
                        alt="trollama"
                        className="h-4 w-4"
                      />
                    ) : (
                      <Cpu className="h-4 w-4" />
                    )}
                    <span>
                      {models.find(m => m.id === selectedModelId)?.name || "Trollama Router (Auto)"}
                    </span>
                  </div>
                  <ChevronDown className="h-4 w-4 opacity-50" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-full min-w-[400px] max-h-64 overflow-y-auto" align="start">
                {models.map((model) => (
                  <DropdownMenuItem
                    key={model.id}
                    onClick={() => setSelectedModelId(model.id)}
                    className={cn(
                      "flex items-center gap-3 p-3 cursor-pointer",
                      model.id === selectedModelId && "bg-secondary"
                    )}
                  >
                    <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-primary/80 to-primary flex items-center justify-center shrink-0">
                      {model.icon === "trollama" ? (
                        <img
                          src="/trollama-badge-no-bg.svg"
                          alt="trollama"
                          className="w-4 h-4"
                        />
                      ) : (
                        <Cpu className="w-3 h-3 text-primary-foreground" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">{model.name}</div>
                    </div>
                    {model.status && (
                      <div className={cn("w-2 h-2 rounded-full shrink-0", model.status)} />
                    )}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <p className="text-sm text-muted-foreground">
              Default model for new conversations. Router mode automatically selects the best model.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
