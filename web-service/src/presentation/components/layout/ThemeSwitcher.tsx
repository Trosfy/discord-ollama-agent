/**
 * Theme Switcher Component
 *
 * Dropdown menu for selecting theme variants.
 * Follows Open/Closed - easy to add new themes via THEME_OPTIONS.
 */

"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { Moon, Sun, Monitor, Palette, Smartphone } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const themes = [
  { value: "light", label: "Light", icon: Sun, description: "Anthropic cream" },
  { value: "dark", label: "Dark", icon: Moon, description: "Anthropic dark" },
  { value: "oled-dark", label: "OLED Dark", icon: Smartphone, description: "True black" },
  { value: "rose-pine", label: "Rosé Pine", icon: Palette, description: "Soft aesthetic" },
  { value: "system", label: "System", icon: Monitor, description: "Match OS" },
] as const;

interface ThemeSwitcherProps {
  /** Show label text next to icon */
  showLabel?: boolean;
  /** Additional className */
  className?: string;
}

export function ThemeSwitcher({ showLabel = false, className }: ThemeSwitcherProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  // Prevent hydration mismatch
  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <Button variant="ghost" size="icon" className={cn("min-h-[44px] min-w-[44px]", className)}>
        <Sun className="h-5 w-5" />
        <span className="sr-only">Toggle theme</span>
      </Button>
    );
  }

  const currentTheme = themes.find((t) => t.value === theme) || themes[0];
  const CurrentIcon = currentTheme.icon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size={showLabel ? "default" : "icon"}
          className={cn("min-h-[44px] gap-2", !showLabel && "min-w-[44px]", className)}
        >
          <CurrentIcon className="h-5 w-5" />
          {showLabel && <span className="text-sm">{currentTheme.label}</span>}
          <span className="sr-only">Toggle theme</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        {themes.map(({ value, label, icon: Icon, description }) => (
          <DropdownMenuItem
            key={value}
            onClick={() => setTheme(value)}
            className={cn(
              "flex items-center gap-3 cursor-pointer py-2",
              theme === value && "bg-accent"
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <div className="flex flex-col min-w-0">
              <span className="text-sm font-medium">{label}</span>
              <span className="text-xs text-muted-foreground truncate">
                {description}
              </span>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
