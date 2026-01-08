"use client";

import { useState } from "react";
import { Activity, Info } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useMonitoring } from "@/contexts/MonitoringContext";

// Type for health check details from backend
interface HealthCheckDetails {
  service?: string;
  timestamp?: string;
  healthy?: boolean | null;
  status_code?: number;
  error?: string;
  skipped?: boolean;
  details?: any;
}

// Type for service display item
interface ServiceItem {
  name: string;
  status: string;
  details: HealthCheckDetails | string | null;
}

export function DashboardServiceHealth() {
  const { data } = useMonitoring();
  const [showDialog, setShowDialog] = useState(false);

  const services = data?.services;

  // Helper function to extract status string from health check object
  const getStatusString = (healthCheck: any): string => {
    if (!healthCheck) return "unknown";

    // If it's already a string (old format), return it
    if (typeof healthCheck === "string") return healthCheck;

    // If it's an object with healthy field (new format)
    if (typeof healthCheck === "object") {
      if (healthCheck.skipped) return "stopped";
      if (healthCheck.healthy === true) return "healthy";
      if (healthCheck.healthy === false) return "unhealthy";
      if (healthCheck.healthy === null) return "stopped";
    }

    return "unknown";
  };

  const serviceArray: ServiceItem[] = services ? [
    { name: "DynamoDB", status: getStatusString(services.dynamodb), details: services.dynamodb || null },
    { name: "Ollama", status: getStatusString(services.ollama), details: services.ollama || null },
    { name: "SGLang", status: getStatusString(services.sglang), details: services.sglang || null },
    { name: "FastAPI", status: getStatusString(services.fastapi), details: services.fastapi || null },
  ] : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Services Health
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
        <div className="space-y-2">
          {serviceArray.length === 0 ? (
            <div className="text-sm text-muted-foreground">Loading...</div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {serviceArray.slice(0, 4).map((service) => (
                <div
                  key={service.name}
                  className="flex items-center gap-2 p-2 rounded-md border"
                >
                  <div
                    className={`h-2 w-2 rounded-full shrink-0 ${
                      service.status === "healthy"
                        ? "bg-primary"
                        : "bg-muted-foreground/40"
                    }`}
                  />
                  <span className="text-xs font-medium truncate">
                    {service.name}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>

      {/* Service Health Details Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Service Health Details
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {serviceArray.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Activity className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p className="text-sm">Loading service data...</p>
              </div>
            ) : (
              <div className="space-y-3">
                {serviceArray.map((service) => (
                  <div
                    key={service.name}
                    className="p-4 bg-secondary/20 rounded-lg"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <div
                            className={`h-3 w-3 rounded-full shrink-0 ${
                              service.status === "healthy"
                                ? "bg-green-500"
                                : "bg-red-500"
                            }`}
                          />
                          <h4 className="font-semibold">{service.name}</h4>
                        </div>
                        <div className="ml-6 space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Status:</span>
                            <span className={`font-medium ${
                              service.status === "healthy"
                                ? "text-green-500"
                                : service.status === "stopped"
                                ? "text-yellow-500"
                                : "text-red-500"
                            }`}>
                              {service.status === "healthy" ? "Healthy" :
                               service.status === "stopped" ? "Stopped (Optional)" :
                               service.status === "unhealthy" ? "Unhealthy" :
                               "Unknown"}
                            </span>
                          </div>
                          {service.details && typeof service.details === "object" && (
                            <>
                              {service.details.status_code && (
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Status Code:</span>
                                  <span className="font-mono text-xs">{service.details.status_code}</span>
                                </div>
                              )}
                              {service.details.error && (
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Error:</span>
                                  <span className="font-mono text-xs text-red-500">{service.details.error}</span>
                                </div>
                              )}
                              {service.details.timestamp && (
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Last Checked:</span>
                                  <span className="text-xs">
                                    {new Date(service.details.timestamp).toLocaleTimeString()}
                                  </span>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
