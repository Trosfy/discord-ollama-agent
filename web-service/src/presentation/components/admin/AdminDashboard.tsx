"use client";

import { DashboardServiceHealth } from "./dashboard/DashboardServiceHealth";
import { DashboardVRAM } from "./dashboard/DashboardVRAM";
import { DashboardPSI } from "./dashboard/DashboardPSI";
import { DashboardDockerContainers } from "./dashboard/DashboardDockerContainers";
import { DashboardModelsQuick } from "./dashboard/DashboardModelsQuick";
import { DashboardSettings } from "./dashboard/DashboardSettings";

export function AdminDashboard() {
  return (
    <div className="w-full min-h-full">
      {/* Container with responsive padding */}
      <div className="container mx-auto p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8">
        {/* Critical Metrics Row - Full width on mobile, 2 cols on tablet+ */}
        <section aria-label="Critical Metrics" className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground/90 hidden sm:block">
            System Status
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            <DashboardServiceHealth />
            <DashboardVRAM />
          </div>
        </section>

        {/* Performance Metrics Row */}
        <section aria-label="Performance Metrics" className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground/90 hidden sm:block">
            Performance & Resources
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            <DashboardPSI />
            <DashboardDockerContainers />
          </div>
        </section>

        {/* Management Section - Stack on mobile, side-by-side on desktop */}
        <section aria-label="Management" className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground/90 hidden sm:block">
            Management & Configuration
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
            <DashboardModelsQuick />
            <DashboardSettings />
          </div>
        </section>
      </div>
    </div>
  );
}
