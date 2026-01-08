/**
 * Theme Provider
 *
 * Wraps next-themes to support multiple theme variants.
 * Follows Single Responsibility - only handles theme context.
 */

"use client";

import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ThemeProviderProps } from "next-themes";

export type Theme = "light" | "dark" | "oled-dark" | "rose-pine" | "system";

export const THEME_OPTIONS = [
  { value: "light", label: "Light", description: "Anthropic cream" },
  { value: "dark", label: "Dark", description: "Anthropic dark" },
  { value: "oled-dark", label: "OLED Dark", description: "True black" },
  { value: "rose-pine", label: "Rosé Pine", description: "Soft aesthetic" },
  { value: "system", label: "System", description: "Match OS" },
] as const;

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      themes={["light", "dark", "oled-dark", "rose-pine"]}
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
