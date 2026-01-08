"use client";

import { useState } from "react";
import { AccountSettings } from "@/components/settings/AccountSettings";
import { ChatSettings } from "@/components/settings/ChatSettings";
import { AppearanceSettings } from "@/components/settings/AppearanceSettings";
import { Button } from "@/components/ui/button";
import { User, MessageSquare, Palette, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type Tab = "account" | "chat" | "appearance";

/**
 * Settings Page
 *
 * Centralized settings management with tabbed interface:
 * - Account: User profile and account details
 * - Chat Preferences: Generation settings, display options
 * - Appearance: Theme and visual customization
 */
export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("account");

  const tabs = [
    {
      id: "account" as Tab,
      label: "Account",
      icon: User,
      mobileLabel: "Account",
    },
    {
      id: "chat" as Tab,
      label: "Chat Preferences",
      icon: MessageSquare,
      mobileLabel: "Chat",
    },
    {
      id: "appearance" as Tab,
      label: "Appearance",
      icon: Palette,
      mobileLabel: "Appearance",
    },
  ];

  return (
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
            activeTab === "account" ? "opacity-100" : "opacity-0 hidden"
          )}
        >
          {activeTab === "account" && (
            <div className="container mx-auto p-4 sm:p-6 lg:p-8">
              <AccountSettings />
            </div>
          )}
        </div>

        <div
          className={cn(
            "transition-opacity duration-200",
            activeTab === "chat" ? "opacity-100" : "opacity-0 hidden"
          )}
        >
          {activeTab === "chat" && (
            <div className="container mx-auto p-4 sm:p-6 lg:p-8">
              <ChatSettings />
            </div>
          )}
        </div>

        <div
          className={cn(
            "transition-opacity duration-200",
            activeTab === "appearance" ? "opacity-100" : "opacity-0 hidden"
          )}
        >
          {activeTab === "appearance" && (
            <div className="container mx-auto p-4 sm:p-6 lg:p-8">
              <AppearanceSettings />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
