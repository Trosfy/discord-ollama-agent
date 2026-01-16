/**
 * Theme - color theme configuration
 */
export type ThemeMode = "dark" | "light" | "auto";

export interface Theme {
  name: string;
  mode: ThemeMode;
  colors: ThemeColors;
}

export interface ThemeColors {
  // Primary colors
  primary: string;
  secondary: string;
  accent: string;

  // Text colors
  text: string;
  textMuted: string;
  textInverse: string;

  // Background colors
  background: string;
  backgroundAlt: string;
  backgroundHighlight: string;

  // Status colors
  success: string;
  warning: string;
  error: string;
  info: string;

  // Border colors
  border: string;
  borderFocus: string;

  // Special
  userMessage: string;
  assistantMessage: string;
  systemMessage: string;
  codeBackground: string;
  code: string;
}

export const DARK_THEME: ThemeColors = {
  primary: "cyan",
  secondary: "magenta",
  accent: "green",

  text: "white",
  textMuted: "gray",
  textInverse: "black",

  background: "black",
  backgroundAlt: "blackBright",
  backgroundHighlight: "blackBright",

  success: "green",
  warning: "yellow",
  error: "red",
  info: "cyan",

  border: "gray",
  borderFocus: "cyan",

  userMessage: "cyan",
  assistantMessage: "green",
  systemMessage: "gray",
  codeBackground: "blackBright",
  code: "yellowBright",
};

export const LIGHT_THEME: ThemeColors = {
  primary: "blue",
  secondary: "magenta",
  accent: "green",

  text: "black",
  textMuted: "gray",
  textInverse: "white",

  background: "white",
  backgroundAlt: "whiteBright",
  backgroundHighlight: "whiteBright",

  success: "green",
  warning: "yellow",
  error: "red",
  info: "blue",

  border: "gray",
  borderFocus: "blue",

  userMessage: "blue",
  assistantMessage: "green",
  systemMessage: "gray",
  codeBackground: "whiteBright",
  code: "yellow",
};

/**
 * Create theme based on mode
 */
export function createTheme(mode: ThemeMode, detected?: "dark" | "light"): Theme {
  const effectiveMode = mode === "auto" ? (detected || "dark") : mode;
  return {
    name: effectiveMode === "dark" ? "Dark" : "Light",
    mode,
    colors: effectiveMode === "dark" ? DARK_THEME : LIGHT_THEME,
  };
}
