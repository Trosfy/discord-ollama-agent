"use client";

import { useState } from "react";
import { HardDrive, Info } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useMonitoring } from "@/contexts/MonitoringContext";

export function DashboardVRAM() {
  const { data } = useMonitoring();
  const [showDialog, setShowDialog] = useState(false);

  const vram = data?.vram;
  const percentage = vram?.usage_percentage || 0;
  const used = vram?.used_gb?.toFixed(1) || "0";
  const total = vram?.total_gb?.toFixed(1) || "0";
  const available = vram?.available_gb?.toFixed(1) || "0";
  const models = vram?.loaded_models || [];

  // Only count models actually loaded in VRAM (not just downloaded)
  const loadedCount = models.filter(m => m.is_loaded).length;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <HardDrive className="h-5 w-5" />
              VRAM Usage
            </CardTitle>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={() => setShowDialog(true)}
            >
              <Info className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {/* Usage bar */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-muted-foreground">
                  {used} / {total} GB
                </span>
                <span className="font-medium">{percentage.toFixed(1)}%</span>
              </div>
              <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>

            {/* Loaded models count */}
            <div className="text-xs text-muted-foreground">
              {loadedCount} model{loadedCount !== 1 ? "s" : ""} loaded
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Details Modal */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <HardDrive className="h-5 w-5" />
              VRAM Usage Details
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {/* Memory stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1">
                <div className="text-sm text-muted-foreground">Total</div>
                <div className="text-2xl font-semibold">{total} GB</div>
              </div>
              <div className="space-y-1">
                <div className="text-sm text-muted-foreground">Used</div>
                <div className="text-2xl font-semibold">{used} GB</div>
              </div>
              <div className="space-y-1">
                <div className="text-sm text-muted-foreground">Available</div>
                <div className="text-2xl font-semibold">{available} GB</div>
              </div>
            </div>

            {/* Usage bar */}
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span>Memory Usage</span>
                <span className="font-medium">{percentage.toFixed(1)}%</span>
              </div>
              <div className="w-full h-4 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${percentage}%` }}
                />
              </div>
            </div>

            {/* Loaded models */}
            {models.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-semibold">Loaded Models ({loadedCount})</h4>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {models
                    .filter(m => m.is_loaded)
                    .map((model, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2 rounded-md bg-secondary/50"
                      >
                        <div className="flex-1">
                          <div className="text-sm font-medium">{model.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {model.backend} • {model.size_gb?.toFixed(1)} GB
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
