"use client";

import { useState } from "react";
import { AdminDashboard } from "@/components/admin/AdminDashboard";
import { UsersManager } from "@/components/admin/UsersManager";
import { Toaster } from "sonner";
import { Button } from "@/components/ui/button";
import { LayoutDashboard, Users, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type Tab = "dashboard" | "users";

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");

  const tabs = [
    {
      id: "dashboard" as Tab,
      label: "Dashboard",
      icon: LayoutDashboard,
      mobileLabel: "Dashboard",
    },
    {
      id: "users" as Tab,
      label: "User Management",
      icon: Users,
      mobileLabel: "Users",
    },
  ];

  return (
    <>
      <div className="flex flex-col h-full">
          {/* Enhanced Navigation Bar */}
          <div className="sticky top-0 z-20 bg-background/95 backdrop-blur-sm border-b">
            <div className="px-4 sm:px-6">
              {/* Desktop Navigation */}
              <nav className="hidden sm:flex items-center gap-1 py-3">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <Button
                      key={tab.id}
                      variant={isActive ? "default" : "ghost"}
                      onClick={() => setActiveTab(tab.id)}
                      className={cn(
                        "h-9 px-4 gap-2 transition-all duration-200",
                        isActive
                          ? "shadow-sm"
                          : "hover:bg-primary/10 hover:text-primary"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      <span className="font-medium">{tab.label}</span>
                    </Button>
                  );
                })}
              </nav>

              {/* Mobile Navigation - Dropdown */}
              <div className="sm:hidden py-3">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      className="w-full justify-between h-10"
                    >
                      <div className="flex items-center gap-2">
                        {tabs.find((t) => t.id === activeTab)?.icon &&
                          (() => {
                            const Icon = tabs.find((t) => t.id === activeTab)!
                              .icon;
                            return <Icon className="h-4 w-4" />;
                          })()}
                        <span className="font-medium">
                          {
                            tabs.find((t) => t.id === activeTab)
                              ?.mobileLabel
                          }
                        </span>
                      </div>
                      <ChevronDown className="h-4 w-4 opacity-50" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent className="w-[calc(100vw-2rem)]" align="start">
                    {tabs.map((tab) => {
                      const Icon = tab.icon;
                      const isActive = activeTab === tab.id;
                      return (
                        <DropdownMenuItem
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={cn(
                            "gap-2 cursor-pointer",
                            isActive && "bg-primary/10 text-primary font-medium"
                          )}
                        >
                          <Icon className="h-4 w-4" />
                          {tab.mobileLabel}
                        </DropdownMenuItem>
                      );
                    })}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </div>

          {/* Tab Content with smooth transitions */}
          <div className="flex-1 overflow-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">
            <div
              className={cn(
                "transition-opacity duration-200",
                activeTab === "dashboard" ? "opacity-100" : "opacity-0 hidden"
              )}
            >
              {activeTab === "dashboard" && <AdminDashboard />}
            </div>

            <div
              className={cn(
                "transition-opacity duration-200",
                activeTab === "users" ? "opacity-100" : "opacity-0 hidden"
              )}
            >
              {activeTab === "users" && (
                <div className="p-4 sm:p-6">
                  <UsersManager />
                </div>
              )}
            </div>
          </div>
        </div>

      <Toaster position="bottom-right" />
    </>
  );
}
