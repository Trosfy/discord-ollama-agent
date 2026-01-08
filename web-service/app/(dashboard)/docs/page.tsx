"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { KeyboardShortcutsTable } from "@/components/docs/KeyboardShortcutsTable";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import {
  BookOpen,
  MessageSquare,
  Keyboard,
  LayoutDashboard,
  HelpCircle,
  ChevronDown,
  Upload,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type Tab = "getting-started" | "chat" | "shortcuts" | "admin" | "faq";

/**
 * Documentation Page
 *
 * Comprehensive guide to Trollama features and usage.
 */
export default function DocsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [activeTab, setActiveTab] = useState<Tab>("getting-started");

  const tabs = [
    {
      id: "getting-started" as Tab,
      label: "Getting Started",
      icon: BookOpen,
      mobileLabel: "Getting Started",
    },
    {
      id: "chat" as Tab,
      label: "Chat Interface",
      icon: MessageSquare,
      mobileLabel: "Chat",
    },
    {
      id: "shortcuts" as Tab,
      label: "Keyboard Shortcuts",
      icon: Keyboard,
      mobileLabel: "Shortcuts",
    },
    ...(isAdmin
      ? [
          {
            id: "admin" as Tab,
            label: "Admin Features",
            icon: LayoutDashboard,
            mobileLabel: "Admin",
          },
        ]
      : []),
    {
      id: "faq" as Tab,
      label: "FAQ",
      icon: HelpCircle,
      mobileLabel: "FAQ",
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
                        const Icon = tabs.find((t) => t.id === activeTab)!.icon;
                        return <Icon className="h-4 w-4" />;
                      })()}
                    <span className="font-medium">
                      {tabs.find((t) => t.id === activeTab)?.mobileLabel}
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
        {/* Getting Started */}
        <div
          className={cn(
            "transition-opacity duration-200",
            activeTab === "getting-started" ? "opacity-100" : "opacity-0 hidden"
          )}
        >
          {activeTab === "getting-started" && (
            <div className="container mx-auto p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8">
              <Card>
                <CardHeader>
                  <CardTitle>Welcome to Trollama!</CardTitle>
                  <CardDescription>Your personal AI workspace powered by advanced language models</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-muted-foreground">
                    Self-hosted AI workspace for homelab enthusiasts.
                  </p>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="p-4 bg-muted rounded-lg">
                      <MessageSquare className="h-6 w-6 mb-2 text-primary" />
                      <h4 className="font-semibold mb-1">Chat Interface</h4>
                      <p className="text-sm text-muted-foreground">
                        Real-time streaming with file attachments
                      </p>
                    </div>

                    <div className="p-4 bg-muted rounded-lg">
                      <Upload className="h-6 w-6 mb-2 text-primary" />
                      <h4 className="font-semibold mb-1">File Uploads</h4>
                      <p className="text-sm text-muted-foreground">
                        PDFs, images, and code analysis
                      </p>
                    </div>

                    <div className="p-4 bg-muted rounded-lg">
                      <Settings className="h-6 w-6 mb-2 text-primary" />
                      <h4 className="font-semibold mb-1">Customization</h4>
                      <p className="text-sm text-muted-foreground">
                        Temperature, models, themes, and display options
                      </p>
                    </div>

                    {isAdmin && (
                      <div className="p-4 bg-muted rounded-lg">
                        <LayoutDashboard className="h-6 w-6 mb-2 text-primary" />
                        <h4 className="font-semibold mb-1">Admin Dashboard</h4>
                        <p className="text-sm text-muted-foreground">
                          System health, model management, and Docker control
                        </p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>

        {/* Chat Interface */}
        <div
          className={cn(
            "transition-opacity duration-200",
            activeTab === "chat" ? "opacity-100" : "opacity-0 hidden"
          )}
        >
          {activeTab === "chat" && (
            <div className="container mx-auto p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8">
              <Card>
                <CardHeader>
                  <CardTitle>Starting a Conversation</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc list-inside space-y-2 text-muted-foreground">
                    <li>Click "New Chat" or press <kbd className="px-2 py-1 text-xs bg-muted rounded">Ctrl+N</kbd></li>
                    <li>Type your message and press Enter or click Send</li>
                    <li>Responses stream in real-time</li>
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>File Attachments</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc list-inside space-y-2 text-muted-foreground">
                    <li>Click the attachment icon (📎) to upload</li>
                    <li>Supported: PDFs, images, text, markdown, code files</li>
                    <li>Supports code analysis, OCR, and PDF reading</li>
                    <li>Files stored in browser (IndexedDB)</li>
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Model Selection</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc list-inside space-y-2 text-muted-foreground">
                    <li><strong>Router (Auto):</strong> Automatically selects best model per query</li>
                    <li><strong>Specific Models:</strong> Choose Qwen, Llama, or DeepSeek directly</li>
                    <li>Change default in Settings → Chat Preferences</li>
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Message Actions</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc list-inside space-y-2 text-muted-foreground">
                    <li><strong>Copy:</strong> Copy message content to clipboard</li>
                    <li><strong>Regenerate:</strong> Get a new response for the same prompt</li>
                    <li><strong>Edit:</strong> Modify your message and branch the conversation</li>
                    <li><strong>Delete:</strong> Remove a message from the conversation</li>
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Conversation Management</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc list-inside space-y-2 text-muted-foreground">
                    <li><strong>Rename:</strong> Edit icon next to conversation title</li>
                    <li><strong>Archive:</strong> Hide without deleting</li>
                    <li><strong>Pin:</strong> Keep at top of list</li>
                    <li><strong>Download:</strong> Export as JSON</li>
                    <li><strong>Clone:</strong> Duplicate conversation</li>
                  </ul>
                </CardContent>
              </Card>
            </div>
          )}
        </div>

        {/* Keyboard Shortcuts */}
        <div
          className={cn(
            "transition-opacity duration-200",
            activeTab === "shortcuts" ? "opacity-100" : "opacity-0 hidden"
          )}
        >
          {activeTab === "shortcuts" && (
            <div className="container mx-auto p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8">
              <Card>
                <CardHeader>
                  <CardTitle>Keyboard Shortcuts</CardTitle>
                  <CardDescription>Speed up your workflow with keyboard shortcuts</CardDescription>
                </CardHeader>
                <CardContent>
                  <KeyboardShortcutsTable />
                </CardContent>
              </Card>
            </div>
          )}
        </div>

        {/* Admin Features (Admin-only) */}
        {isAdmin && (
          <div
            className={cn(
              "transition-opacity duration-200",
              activeTab === "admin" ? "opacity-100" : "opacity-0 hidden"
            )}
          >
            {activeTab === "admin" && (
              <div className="container mx-auto p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8">
                <Card>
                  <CardHeader>
                    <CardTitle>Dashboard Overview</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-muted-foreground mb-4">
                      Real-time monitoring with automatic updates.
                    </p>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="p-4 bg-muted rounded-lg">
                        <h4 className="font-semibold mb-2">Service Health</h4>
                        <p className="text-sm text-muted-foreground">
                          Monitor FastAPI, Auth, Admin, and Discord services.
                        </p>
                      </div>

                      <div className="p-4 bg-muted rounded-lg">
                        <h4 className="font-semibold mb-2">VRAM Monitor</h4>
                        <p className="text-sm text-muted-foreground">
                          Real-time GPU memory usage tracking.
                        </p>
                      </div>

                      <div className="p-4 bg-muted rounded-lg">
                        <h4 className="font-semibold mb-2">PSI Metrics</h4>
                        <p className="text-sm text-muted-foreground">
                          CPU, memory, and I/O resource pressure monitoring.
                        </p>
                      </div>

                      <div className="p-4 bg-muted rounded-lg">
                        <h4 className="font-semibold mb-2">Docker Control</h4>
                        <p className="text-sm text-muted-foreground">
                          Start, stop, and restart containers.
                        </p>
                      </div>

                      <div className="p-4 bg-muted rounded-lg">
                        <h4 className="font-semibold mb-2">Model Management</h4>
                        <p className="text-sm text-muted-foreground">
                          Load and unload models with VRAM tracking.
                        </p>
                      </div>

                      <div className="p-4 bg-muted rounded-lg">
                        <h4 className="font-semibold mb-2">User Management</h4>
                        <p className="text-sm text-muted-foreground">
                          Manage users, tokens, and access control.
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        )}

        {/* FAQ */}
        <div
          className={cn(
            "transition-opacity duration-200",
            activeTab === "faq" ? "opacity-100" : "opacity-0 hidden"
          )}
        >
          {activeTab === "faq" && (
            <div className="container mx-auto p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8">
              <Card>
                <CardHeader>
                  <CardTitle>Frequently Asked Questions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div>
                    <h4 className="font-semibold mb-2">Q: What models are supported?</h4>
                    <p className="text-muted-foreground">
                      A: Any Ollama-compatible model. Common options include Qwen 2.5, Llama 3.1, and DeepSeek R1. Router mode automatically selects the best model per query.
                    </p>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-2">Q: Where are conversations stored?</h4>
                    <p className="text-muted-foreground">
                      A: Backend database with browser localStorage sync. File attachments in IndexedDB.
                    </p>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-2">Q: Does it work on mobile?</h4>
                    <p className="text-muted-foreground">
                      A: Yes. Fully responsive with collapsible sidebar and touch controls.
                    </p>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-2">Q: How do I change the theme?</h4>
                    <p className="text-muted-foreground">
                      A: Settings → Appearance. Choose Light, Dark, or System (matches OS).
                    </p>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-2">Q: What is temperature?</h4>
                    <p className="text-muted-foreground">
                      A: Controls response randomness. Lower = focused, higher = creative. Default: 0.7.
                    </p>
                  </div>

                  <div>
                    <h4 className="font-semibold mb-2">Q: What is thinking mode?</h4>
                    <p className="text-muted-foreground">
                      A: Extended reasoning for complex queries. Slower but more thorough responses.
                    </p>
                  </div>

                  {isAdmin && (
                    <div>
                      <h4 className="font-semibold mb-2">Q: How do I monitor system resources?</h4>
                      <p className="text-muted-foreground">
                        A: Admin Dashboard shows real-time VRAM, PSI metrics, service health, and Docker status.
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>

            </div>
          )}
        </div>
      </div>
    </div>
  );
}
