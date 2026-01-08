"use client";

import { useSettingsStore } from "@/stores/settingsStore";
import { useTheme } from "next-themes";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Palette, Sun, Moon, Monitor } from "lucide-react";
import { useEffect } from "react";

/**
 * Appearance Settings Component
 *
 * Configure visual appearance: theme, colors, layout preferences.
 */
export function AppearanceSettings() {
  const { theme: settingsTheme, setTheme: setSettingsTheme } = useSettingsStore();
  const { theme: activeTheme, setTheme, themes } = useTheme();

  // Sync settings store with next-themes
  useEffect(() => {
    if (settingsTheme !== activeTheme) {
      setTheme(settingsTheme);
    }
  }, [settingsTheme, activeTheme, setTheme]);

  const handleThemeChange = (newTheme: "light" | "dark" | "system") => {
    setSettingsTheme(newTheme);
    setTheme(newTheme);
  };

  const themeOptions = [
    {
      value: "light" as const,
      label: "Light",
      description: "Light background",
      icon: Sun,
    },
    {
      value: "dark" as const,
      label: "Dark",
      description: "Dark background",
      icon: Moon,
    },
    {
      value: "system" as const,
      label: "System",
      description: "Match system settings",
      icon: Monitor,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Theme Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            Theme
          </CardTitle>
          <CardDescription>
            Choose your preferred color scheme
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {themeOptions.map((option) => {
              const Icon = option.icon;
              const isSelected = settingsTheme === option.value;

              return (
                <button
                  key={option.value}
                  onClick={() => handleThemeChange(option.value)}
                  className={`
                    relative flex flex-col items-center gap-3 p-4 rounded-lg border-2 transition-all
                    ${
                      isSelected
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50 hover:bg-muted"
                    }
                  `}
                >
                  <Icon className={`h-8 w-8 ${isSelected ? "text-primary" : "text-muted-foreground"}`} />
                  <div className="text-center">
                    <div className={`font-medium ${isSelected ? "text-primary" : ""}`}>
                      {option.label}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {option.description}
                    </div>
                  </div>
                  {isSelected && (
                    <div className="absolute top-2 right-2 h-2 w-2 rounded-full bg-primary" />
                  )}
                </button>
              );
            })}
          </div>

        </CardContent>
      </Card>

    </div>
  );
}
