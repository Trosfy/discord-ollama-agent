import type { ThemeMode } from "@domain/value-objects";

/**
 * Configuration store interface for persisting user settings.
 */
export interface IConfigStore {
  /**
   * Get the full configuration
   */
  getConfig(): Promise<AppConfig>;

  /**
   * Save the full configuration
   */
  saveConfig(config: AppConfig): Promise<void>;

  /**
   * Get active profile
   */
  getActiveProfile(): Promise<Profile>;

  /**
   * Get profile by name
   */
  getProfile(name: string): Promise<Profile | undefined>;

  /**
   * List all profiles
   */
  listProfiles(): Promise<ProfileSummary[]>;

  /**
   * Save a profile
   */
  saveProfile(profile: Profile): Promise<void>;

  /**
   * Delete a profile
   */
  deleteProfile(name: string): Promise<void>;

  /**
   * Set active profile
   */
  setActiveProfile(name: string): Promise<void>;

  /**
   * Get server configuration by name
   */
  getServer(name: string): Promise<ServerConfig | undefined>;

  /**
   * List all server configurations
   */
  listServers(): Promise<ServerConfig[]>;

  /**
   * Save server configuration
   */
  saveServer(server: ServerConfig): Promise<void>;

  /**
   * Delete server configuration
   */
  deleteServer(name: string): Promise<void>;

  /**
   * Set active server
   */
  setActiveServer(name: string): Promise<void>;
}

/**
 * Root application configuration
 */
export interface AppConfig {
  version: string;
  activeProfile: string;
  activeServer: string;
  profiles: Record<string, Profile>;
  servers: Record<string, ServerConfig>;
  ui: UIConfig;
}

/**
 * User profile configuration
 */
export interface Profile {
  name: string;
  description?: string;

  model: ModelConfig;
  execution: ExecutionConfig;
  ui: UIConfig;

  /** Custom system prompt to prepend */
  systemPrompt?: string;
}

export interface ModelConfig {
  /** Model name/id */
  name: string;
  /** Temperature (0.0-1.0) */
  temperature: number;
  /** Max tokens for response */
  maxTokens: number;
  /** Show <think> blocks */
  showThinking: boolean;
  /** Number of messages to include in context */
  contextLength: number;
}

export interface ExecutionConfig {
  /** Shell to use for commands */
  shell: string;
  /** Default working directory */
  workingDir: string;
  /** Command timeout in seconds */
  commandTimeout: number;
  /** Require approval for dangerous commands */
  requireApproval: boolean;
  /** Custom dangerous command patterns */
  dangerousPatterns?: string[];
}

export interface UIConfig {
  /** Theme mode */
  theme: ThemeMode;
  /** Syntax highlighting theme */
  syntaxTheme: string;
  /** Show timestamps on messages */
  showTimestamps: boolean;
  /** Streaming display throttle (ms) */
  streamingSpeed: number;
  /** Split view settings */
  splitView: SplitViewConfig;
}

export interface SplitViewConfig {
  enabled: boolean;
  layout: "horizontal" | "vertical";
  ratio: number;
  leftPanel: string;
  rightPanel: string;
  rememberLast: boolean;
}

/**
 * Server connection configuration
 */
export interface ServerConfig {
  name: string;
  url: string;
  description?: string;
  /** API key for remote servers (future) */
  apiKey?: string;
  /** Whether this is the default server */
  default?: boolean;
}

/**
 * Profile summary for listing
 */
export interface ProfileSummary {
  name: string;
  description?: string;
  isActive: boolean;
}

/**
 * Default configuration
 */
export const DEFAULT_CONFIG: AppConfig = {
  version: "1.0.0",
  activeProfile: "default",
  activeServer: "local",
  profiles: {
    default: {
      name: "default",
      description: "Default balanced profile",
      model: {
        name: "qwen3:30b",
        temperature: 0.7,
        maxTokens: 4096,
        showThinking: false,
        contextLength: 20,
      },
      execution: {
        shell: "bash",
        workingDir: "~",
        commandTimeout: 300,
        requireApproval: true,
      },
      ui: {
        theme: "auto",
        syntaxTheme: "monokai",
        showTimestamps: true,
        streamingSpeed: 0,
        splitView: {
          enabled: false,
          layout: "horizontal",
          ratio: 50,
          leftPanel: "chat",
          rightPanel: "files",
          rememberLast: true,
        },
      },
    },
  },
  servers: {
    local: {
      name: "local",
      url: "ws://localhost:8001",
      description: "Local development server",
      default: true,
    },
  },
  ui: {
    theme: "auto",
    syntaxTheme: "monokai",
    showTimestamps: true,
    streamingSpeed: 0,
    splitView: {
      enabled: false,
      layout: "horizontal",
      ratio: 50,
      leftPanel: "chat",
      rightPanel: "files",
      rememberLast: true,
    },
  },
};
