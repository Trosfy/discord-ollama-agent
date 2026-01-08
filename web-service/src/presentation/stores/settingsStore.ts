"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsState {
  // Generation settings
  temperature: number;
  thinkingEnabled: boolean;
  selectedModelId: string;

  // Appearance settings
  theme: "light" | "dark" | "system";
  compactMode: boolean;
  showTimestamps: boolean;

  // Actions
  setTemperature: (temp: number) => void;
  setThinkingEnabled: (enabled: boolean) => void;
  setSelectedModelId: (modelId: string) => void;
  setTheme: (theme: "light" | "dark" | "system") => void;
  setCompactMode: (enabled: boolean) => void;
  setShowTimestamps: (enabled: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      // Defaults
      temperature: 0.7,
      thinkingEnabled: true,
      selectedModelId: "trollama",
      theme: "system",
      compactMode: false,
      showTimestamps: true,

      // Actions
      setTemperature: (temp: number) =>
        set({ temperature: Math.max(0, Math.min(2, temp)) }), // Clamp 0-2

      setThinkingEnabled: (enabled: boolean) => set({ thinkingEnabled: enabled }),

      setSelectedModelId: (modelId: string) => set({ selectedModelId: modelId }),

      setTheme: (theme: "light" | "dark" | "system") => set({ theme }),

      setCompactMode: (enabled: boolean) => set({ compactMode: enabled }),

      setShowTimestamps: (enabled: boolean) => set({ showTimestamps: enabled }),
    }),
    {
      name: "chat-settings", // localStorage key
      partialize: (state) => ({
        temperature: state.temperature,
        thinkingEnabled: state.thinkingEnabled,
        selectedModelId: state.selectedModelId,
        theme: state.theme,
        compactMode: state.compactMode,
        showTimestamps: state.showTimestamps,
      }),
    }
  )
);
