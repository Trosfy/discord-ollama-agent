"use client";

import { useState } from "react";
import { useSettingsStore } from "@/stores/settingsStore";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  PanelLeft,
  Plus,
  SlidersHorizontal,
  Settings,
  Archive,
  BookOpen,
  Keyboard,
  LogOut,
  User,
  Sparkles,
  Brain,
} from "lucide-react";
import { IconButton } from "@/presentation/components/ui/IconButton";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { useConversationStore } from "@/stores/conversationStore";
import { KeyboardShortcutsModal } from "@/components/modals/KeyboardShortcutsModal";
import { cn } from "@/lib/utils";

interface TopBarProps {
  onMenuClick: () => void;
  isMobile: boolean;
  isSidebarOpen: boolean;
}

export function TopBar({ onMenuClick, isMobile, isSidebarOpen }: TopBarProps) {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { conversations, addConversation, setCurrentConversation } = useConversationStore();
  const [showShortcuts, setShowShortcuts] = useState(false);

  // Settings from store (persisted to localStorage)
  const { temperature, thinkingEnabled, setTemperature, setThinkingEnabled } = useSettingsStore();

  const handleNewChat = () => {
    // Check if there's already an empty "New Chat" conversation
    const emptyNewChat = conversations.find(
      (conv) =>
        conv.title === "New Chat" &&
        !conv.archived &&
        (!conv.messages || conv.messages.length === 0)
    );

    if (emptyNewChat) {
      // Reuse existing empty conversation
      setCurrentConversation(emptyNewChat.id);
      router.push(`/chat/${emptyNewChat.id}`);
    } else {
      // Create new conversation
      const newConversation = {
        id: Date.now().toString(),
        title: "New Chat",
        createdAt: new Date(),
        updatedAt: new Date(),
        archived: false,
      };
      addConversation(newConversation);
      router.push(`/chat/${newConversation.id}`);
    }
  };

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  // Check if user is admin
  const isAdmin = user?.role === "admin";

  return (
    <header className="sticky top-0 z-30 bg-background/95 backdrop-blur-sm h-14 flex items-center justify-between px-3">
      {/* Left section */}
      <div className="flex items-center gap-2">
        {/* Sidebar toggle - fades in/out smoothly to prevent layout shift */}
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "h-10 w-10 rounded-xl shrink-0 transition-opacity duration-200",
            (!isSidebarOpen || isMobile) ? "opacity-100" : "opacity-0 pointer-events-none"
          )}
          onClick={onMenuClick}
          tabIndex={(!isSidebarOpen || isMobile) ? 0 : -1}
        >
          <PanelLeft className="h-5 w-5" />
          <span className="sr-only">Toggle sidebar</span>
        </Button>

        {/* Trollama branding */}
        <img
          src="/trollama-badge-no-bg.svg"
          alt="Trollama"
          className="h-5 w-5"
        />
        <span className="text-lg font-semibold tracking-tight">Trollama</span>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-1">
      {/* New Chat Button */}
      <Button
        variant="ghost"
        size="icon"
        className="h-10 w-10 rounded-xl"
        onClick={handleNewChat}
        title="New chat"
      >
        <Plus className="h-5 w-5" />
        <span className="sr-only">New chat</span>
      </Button>

      {/* Controls Dropdown */}
      <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10 rounded-xl"
              title="Chat controls"
            >
              <SlidersHorizontal className="h-5 w-5" />
              <span className="sr-only">Controls</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64 p-3">
            <div className="text-xs font-medium text-muted-foreground mb-3">Chat Controls</div>

            {/* Temperature */}
            <div className="space-y-2 mb-4">
              <div className="flex items-center justify-between">
                <span className="text-sm flex items-center gap-2">
                  <Sparkles className="w-4 h-4" />
                  Temperature
                </span>
                <span className="text-sm text-muted-foreground">{temperature}</span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer accent-primary"
              />
            </div>

            {/* Thinking/Reasoning Toggle */}
            <div className="flex items-center justify-between">
              <span className="text-sm flex items-center gap-2">
                <Brain className="w-4 h-4" />
                Thinking
              </span>
              <input
                type="range"
                min="0"
                max="1"
                step="1"
                value={thinkingEnabled ? 1 : 0}
                onChange={(e) => setThinkingEnabled(parseInt(e.target.value) === 1)}
                className="w-10 h-2 bg-secondary rounded-lg appearance-none cursor-pointer transition-colors"
                style={{ accentColor: thinkingEnabled ? 'var(--primary)' : 'var(--muted-foreground)' }}
              />
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

      {/* User Avatar Dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <IconButton
            size="lg"
            title={user?.displayName || user?.username || "Account"}
          >
            <User />
            <span className="sr-only">Account menu</span>
          </IconButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          {/* User info */}
          {user && (
            <>
              <div className="px-3 py-2">
                <div className="font-medium text-sm">{user.displayName || user.username}</div>
                <div className="text-xs text-muted-foreground">{user.email || user.username}</div>
              </div>
              <DropdownMenuSeparator />
            </>
          )}

          <DropdownMenuItem onClick={() => router.push("/settings")}>
            <Settings className="w-4 h-4 mr-2" />
            Settings
          </DropdownMenuItem>
          
          <DropdownMenuItem onClick={() => router.push("/chat/archived")}>
            <Archive className="w-4 h-4 mr-2" />
            Archived Chats
          </DropdownMenuItem>

          {isAdmin && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => router.push("/admin")}>
                <Settings className="w-4 h-4 mr-2" />
                Admin Panel
              </DropdownMenuItem>
            </>
          )}

          <DropdownMenuSeparator />
          
          <DropdownMenuItem onClick={() => router.push("/docs")}>
            <BookOpen className="w-4 h-4 mr-2" />
            Documentation
          </DropdownMenuItem>

          <DropdownMenuItem onClick={() => setShowShortcuts(true)}>
            <Keyboard className="w-4 h-4 mr-2" />
            Keyboard shortcuts
          </DropdownMenuItem>

          <DropdownMenuSeparator />

          <DropdownMenuItem onClick={handleLogout} className="text-destructive">
            <LogOut className="w-4 h-4 mr-2" />
            Sign Out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      </div>

      {/* Keyboard Shortcuts Modal */}
      <KeyboardShortcutsModal open={showShortcuts} onOpenChange={setShowShortcuts} />
    </header>
  );
}
