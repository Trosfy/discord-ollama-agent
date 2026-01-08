"use client";

import { useState } from "react";
import { Settings, Info } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function DashboardSettings() {
  const [showDialog, setShowDialog] = useState(false);
  const [maintenanceMode, setMaintenanceMode] = useState(false);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Quick Settings
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
          {/* Quick toggles */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm">Maintenance Mode</span>
              <input
                type="checkbox"
                checked={maintenanceMode}
                onChange={(e) => setMaintenanceMode(e.target.checked)}
                className="w-4 h-4 accent-primary cursor-pointer"
              />
            </div>
          </div>
        </div>
      </CardContent>

      {/* Configuration Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              System Configuration
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6">
            {/* Maintenance Settings */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Maintenance Settings</h3>
              <div className="space-y-3 p-4 bg-secondary/20 rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium">Maintenance Mode</div>
                    <div className="text-xs text-muted-foreground">
                      Disable incoming requests during maintenance
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={maintenanceMode}
                    onChange={(e) => setMaintenanceMode(e.target.checked)}
                    className="w-5 h-5 accent-primary cursor-pointer"
                  />
                </div>
                {maintenanceMode && (
                  <div className="text-xs bg-amber-500/10 text-amber-600 dark:text-amber-400 p-3 rounded">
                    ⚠️ Maintenance mode is active. All incoming requests will be rejected.
                  </div>
                )}
              </div>
            </div>

            {/* Performance Settings */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Performance Profile</h3>
              <div className="space-y-2 p-4 bg-secondary/20 rounded-lg">
                <div className="text-xs text-muted-foreground mb-2">
                  Active profile determines model routing and resource allocation
                </div>
                <div className="space-y-2">
                  <label className="flex items-center gap-3 p-2 rounded hover:bg-secondary/50 cursor-pointer">
                    <input
                      type="radio"
                      name="profile"
                      value="performance"
                      className="w-4 h-4 accent-primary"
                      defaultChecked
                    />
                    <div>
                      <div className="text-sm font-medium">Performance</div>
                      <div className="text-xs text-muted-foreground">
                        Uses high-performance SGLang models (requires more VRAM)
                      </div>
                    </div>
                  </label>
                  <label className="flex items-center gap-3 p-2 rounded hover:bg-secondary/50 cursor-pointer">
                    <input
                      type="radio"
                      name="profile"
                      value="conservative"
                      className="w-4 h-4 accent-primary"
                    />
                    <div>
                      <div className="text-sm font-medium">Conservative</div>
                      <div className="text-xs text-muted-foreground">
                        Uses Ollama models (lower VRAM usage, slower)
                      </div>
                    </div>
                  </label>
                </div>
              </div>
            </div>

            {/* Logging Settings */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Logging & Monitoring</h3>
              <div className="space-y-3 p-4 bg-secondary/20 rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium">Debug Logging</div>
                    <div className="text-xs text-muted-foreground">
                      Enable verbose logging for troubleshooting
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    className="w-5 h-5 accent-primary cursor-pointer"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium">Metrics Collection</div>
                    <div className="text-xs text-muted-foreground">
                      Collect detailed performance metrics
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    defaultChecked
                    className="w-5 h-5 accent-primary cursor-pointer"
                  />
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-2 pt-4 border-t">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setShowDialog(false)}
              >
                Cancel
              </Button>
              <Button
                variant="default"
                className="flex-1"
                onClick={() => {
                  // TODO: Save configuration
                  setShowDialog(false);
                }}
              >
                Save Changes
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
