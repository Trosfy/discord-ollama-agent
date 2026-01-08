/**
 * Application Constants
 *
 * Central configuration for app-wide constants.
 * Part of the Config Layer (SOLID Architecture)
 */

export const APP_NAME = "Trollama";
export const APP_DESCRIPTION = "Your intelligent AI agent workspace powered by advanced language models";

// Available models
export const AVAILABLE_MODELS = [
  "llama2",
  "mistral",
  "codellama",
  "deepseek-coder",
  "qwen",
] as const;

// Theme
export const DEFAULT_THEME = "light" as const;
export const THEMES = ["light", "dark", "system"] as const;

// Chat settings
export const DEFAULT_TEMPERATURE = 0.7;
export const MIN_TEMPERATURE = 0.0;
export const MAX_TEMPERATURE = 2.0;

export const DEFAULT_THINKING_MODE = "auto" as const;
export const THINKING_MODES = ["auto", "enabled", "disabled"] as const;

// Pagination
export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

// LocalStorage keys
export const STORAGE_KEYS = {
  AUTH_TOKEN: "trollama_auth_token",
  REFRESH_TOKEN: "trollama_refresh_token",
  USER: "trollama_user",
  THEME: "trollama_theme",
  LAST_CONVERSATION: "trollama_last_conversation",
} as const;

// Responsive breakpoints (matches Tailwind CSS v4 config)
export const BREAKPOINTS = {
  SM: 640,
  MD: 768,
  LG: 1024,
  XL: 1280,
  "2XL": 1536,
} as const;

// Touch target size (Apple HIG)
export const MIN_TOUCH_TARGET = 44; // pixels

// Animation durations
export const ANIMATION = {
  FAST: 150,
  BASE: 250,
  SLOW: 350,
} as const;
