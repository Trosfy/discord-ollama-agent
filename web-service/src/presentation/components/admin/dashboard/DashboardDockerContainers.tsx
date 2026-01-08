"use client";

import { Server } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useDockerContainers } from "@/hooks/useDockerContainers";
import { useDockerMaster } from "@/hooks/useDockerMaster";
import { toast } from "sonner";
import { useState } from "react";

export function DashboardDockerContainers() {
  const { containers, loading, transitioning, startContainer, stopContainer, refresh } = useDockerContainers();
  const { startAll, stopAll } = useDockerMaster();
  const [masterLoading, setMasterLoading] = useState<"starting" | "stopping" | null>(null);

  const handleToggle = async (name: string, isRunning: boolean) => {
    console.log(`[DashboardDockerContainers] handleToggle called: ${name}, isRunning=${isRunning}`);
    try {
      if (isRunning) {
        console.log(`[DashboardDockerContainers] Starting container: ${name}`);
        await startContainer(name);
        toast.success(`Started ${name.replace("trollama-", "")}`);
      } else {
        console.log(`[DashboardDockerContainers] Stopping container: ${name}`);
        await stopContainer(name);
        toast.success(`Stopped ${name.replace("trollama-", "")}`);
      }
    } catch (err) {
      console.error(`[DashboardDockerContainers] Error toggling ${name}:`, err);
      toast.error(`Failed to ${isRunning ? 'start' : 'stop'} ${name.replace("trollama-", "")}`);
    }
  };

  const handleMasterToggle = async (shouldStart: boolean) => {
    setMasterLoading(shouldStart ? "starting" : "stopping");
    try {
      if (shouldStart) {
        await startAll();
        toast.success("All services operational");
      } else {
        await stopAll();
        toast.success("All services stopped");
      }
      // Refresh container list after delay to allow containers to start/stop
      setTimeout(refresh, 2000);
    } catch (err) {
      toast.error(`Failed to ${shouldStart ? 'start' : 'stop'} all services`);
    } finally {
      setMasterLoading(null);
    }
  };

  // Calculate master switch state: ON if majority of containers are running
  const runningCount = containers.filter(c => c.state === "running").length;
  const isMasterOn = runningCount > containers.length / 2;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Server className="h-5 w-5" />
          Docker Containers
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-sm text-muted-foreground">Loading...</div>
        ) : (
          <div className="space-y-3">
            {/* Master Toggle */}
            {containers.length > 0 && (
              <div className="pb-3 border-b border-border">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold flex-1">Master Control</span>
                  <div className="text-xs font-mono shrink-0">
                    {masterLoading && (
                      <span className="text-amber-500 animate-pulse">
                        {masterLoading === "starting" ? "Starting..." : "Stopping..."}
                      </span>
                    )}
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="1"
                    value={isMasterOn ? 1 : 0}
                    onChange={(e) => handleMasterToggle(parseInt(e.target.value) === 1)}
                    disabled={masterLoading !== null}
                    className="w-10 h-2 bg-secondary rounded-lg appearance-none cursor-pointer transition-colors shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{ accentColor: isMasterOn ? 'var(--primary)' : 'var(--muted-foreground)' }}
                  />
                </div>
              </div>
            )}

            {/* Individual Container Toggles */}
            <div className="space-y-2">
              {containers.length === 0 ? (
                <div className="text-sm text-muted-foreground">No containers found</div>
              ) : (
                containers.map((container) => {
                  const transitionAction = transitioning.get(container.name);
                  const isTransitioning = transitionAction !== undefined;
                  const isRunning = container.state === "running";

                  return (
                    <div
                      key={container.name}
                      className="flex items-center justify-between gap-2"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm truncate">
                          {container.name.replace("trollama-", "")}
                        </div>
                        {container.memory && (
                          <div className="text-xs text-muted-foreground">
                            {container.memory.usage}
                          </div>
                        )}
                      </div>
                      <div className="text-xs font-mono shrink-0">
                        {isTransitioning ? (
                          <span className="text-amber-500 animate-pulse">
                            {transitionAction === "starting" ? "Starting..." : "Stopping..."}
                          </span>
                        ) : container.memory ? (
                          <span className="text-muted-foreground">
                            {container.memory.percentage}
                          </span>
                        ) : null}
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="1"
                        value={isRunning ? 1 : 0}
                        onChange={(e) => {
                          console.log(`[DashboardDockerContainers] onChange fired for ${container.name}: value=${e.target.value}, state=${container.state}`);
                          handleToggle(container.name, parseInt(e.target.value) === 1);
                        }}
                        disabled={isTransitioning}
                        className="w-10 h-2 bg-secondary rounded-lg appearance-none cursor-pointer transition-colors shrink-0 disabled:opacity-50 disabled:cursor-wait"
                        style={{ accentColor: isRunning ? 'var(--primary)' : 'var(--muted-foreground)' }}
                      />
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
