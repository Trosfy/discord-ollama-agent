"use client";

import { useState } from "react";
import { Gauge, Info } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useMonitoring } from "@/contexts/MonitoringContext";

export function DashboardPSI() {
  const { data } = useMonitoring();
  const [showDialog, setShowDialog] = useState(false);

  const cpuUtil = data?.cpu_utilization || 0;
  const gpuUtil = data?.gpu?.utilization_pct || 0;
  const gpuTemp = data?.gpu?.temperature_c || 0;
  const gpuPower = data?.gpu?.power_draw_w || 0;
  const psi = data?.psi || { cpu: 0, memory: 0, io: 0 };

  const getCPUColor = (value: number) => {
    if (value < 30) return "text-primary";
    if (value < 70) return "text-muted-foreground";
    return "text-muted-foreground/60";
  };

  const getTempColor = (value: number) => {
    if (value < 70) return "text-primary";
    if (value < 85) return "text-muted-foreground";
    return "text-muted-foreground/60";
  };

  const getPSIColor = (value: number) => {
    if (value < 10) return "text-primary";
    if (value < 50) return "text-amber-500";
    return "text-red-500";
  };

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Gauge className="h-5 w-5" />
              System Metrics
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
            {/* System metrics: CPU, GPU, Temp, Power */}
            <div className="grid grid-cols-4 gap-2 text-center">
              <div>
                <div className="text-xs text-muted-foreground mb-1">CPU</div>
                <div className={`text-lg font-semibold ${getCPUColor(cpuUtil)}`}>
                  {cpuUtil.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">GPU</div>
                <div className={`text-lg font-semibold ${getCPUColor(gpuUtil)}`}>
                  {gpuUtil.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Temp</div>
                <div className={`text-lg font-semibold ${getTempColor(gpuTemp)}`}>
                  {gpuTemp}°C
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground mb-1">Power</div>
                <div className="text-lg font-semibold text-primary">
                  {gpuPower.toFixed(1)}W
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Details Modal */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Gauge className="h-5 w-5" />
              System Metrics Details
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-6">
            {/* System metrics */}
            <div>
              <h4 className="text-sm font-semibold mb-3">Resource Utilization</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <div className="text-sm text-muted-foreground">CPU</div>
                  <div className={`text-3xl font-semibold ${getCPUColor(cpuUtil)}`}>
                    {cpuUtil.toFixed(1)}%
                  </div>
                  <div className="w-full h-2 bg-secondary rounded-full overflow-hidden mt-2">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${cpuUtil}%` }}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-sm text-muted-foreground">GPU</div>
                  <div className={`text-3xl font-semibold ${getCPUColor(gpuUtil)}`}>
                    {gpuUtil.toFixed(1)}%
                  </div>
                  <div className="w-full h-2 bg-secondary rounded-full overflow-hidden mt-2">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${gpuUtil}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* GPU thermal/power */}
            <div>
              <h4 className="text-sm font-semibold mb-3">GPU Thermal & Power</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <div className="text-sm text-muted-foreground">Temperature</div>
                  <div className={`text-3xl font-semibold ${getTempColor(gpuTemp)}`}>
                    {gpuTemp}°C
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    {gpuTemp < 70 ? "Normal" : gpuTemp < 85 ? "Warm" : "Hot"}
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-sm text-muted-foreground">Power Draw</div>
                  <div className="text-3xl font-semibold text-primary">
                    {gpuPower.toFixed(1)}W
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    Current draw
                  </div>
                </div>
              </div>
            </div>

            {/* PSI Pressure Metrics */}
            <div>
              <h4 className="text-sm font-semibold mb-3">Pressure Stall Information (PSI)</h4>
              <div className="space-y-3">
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">CPU Pressure</span>
                    <span className={`font-medium ${getPSIColor(psi.cpu)}`}>
                      {psi.cpu.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${psi.cpu < 10 ? 'bg-primary' : psi.cpu < 50 ? 'bg-amber-500' : 'bg-red-500'}`}
                      style={{ width: `${Math.min(psi.cpu, 100)}%` }}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Memory Pressure</span>
                    <span className={`font-medium ${getPSIColor(psi.memory)}`}>
                      {psi.memory.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${psi.memory < 10 ? 'bg-primary' : psi.memory < 50 ? 'bg-amber-500' : 'bg-red-500'}`}
                      style={{ width: `${Math.min(psi.memory, 100)}%` }}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">I/O Pressure</span>
                    <span className={`font-medium ${getPSIColor(psi.io)}`}>
                      {psi.io.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${psi.io < 10 ? 'bg-primary' : psi.io < 50 ? 'bg-amber-500' : 'bg-red-500'}`}
                      style={{ width: `${Math.min(psi.io, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
              <div className="mt-3 text-xs text-muted-foreground">
                PSI measures system resource contention. Lower is better.
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
