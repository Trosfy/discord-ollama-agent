import Conf from "conf";
import type {
  IConfigStore,
  AppConfig,
  Profile,
  ProfileSummary,
  ServerConfig,
  DEFAULT_CONFIG,
} from "@application/ports";

/**
 * Local configuration store using Conf (electron-store compatible).
 * Stores configuration in ~/.config/troise-tui/config.json
 */
export class LocalConfigStore implements IConfigStore {
  private store: Conf<AppConfig>;

  constructor() {
    this.store = new Conf<AppConfig>({
      projectName: "troise-tui",
      defaults: {
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
      },
    });
  }

  async getConfig(): Promise<AppConfig> {
    return this.store.store;
  }

  async saveConfig(config: AppConfig): Promise<void> {
    this.store.store = config;
  }

  async getActiveProfile(): Promise<Profile> {
    const config = this.store.store;
    const profileName = config.activeProfile;
    const profile = config.profiles[profileName];

    if (!profile) {
      // Return default profile
      return config.profiles.default;
    }

    return profile;
  }

  async getProfile(name: string): Promise<Profile | undefined> {
    const config = this.store.store;
    return config.profiles[name];
  }

  async listProfiles(): Promise<ProfileSummary[]> {
    const config = this.store.store;
    const activeProfile = config.activeProfile;

    return Object.values(config.profiles).map((profile) => ({
      name: profile.name,
      description: profile.description,
      isActive: profile.name === activeProfile,
    }));
  }

  async saveProfile(profile: Profile): Promise<void> {
    const config = this.store.store;
    config.profiles[profile.name] = profile;
    this.store.store = config;
  }

  async deleteProfile(name: string): Promise<void> {
    if (name === "default") {
      throw new Error("Cannot delete default profile");
    }

    const config = this.store.store;

    if (config.activeProfile === name) {
      config.activeProfile = "default";
    }

    delete config.profiles[name];
    this.store.store = config;
  }

  async setActiveProfile(name: string): Promise<void> {
    const config = this.store.store;

    if (!config.profiles[name]) {
      throw new Error(`Profile not found: ${name}`);
    }

    config.activeProfile = name;
    this.store.store = config;
  }

  async getServer(name: string): Promise<ServerConfig | undefined> {
    const config = this.store.store;
    return config.servers[name];
  }

  async listServers(): Promise<ServerConfig[]> {
    const config = this.store.store;
    return Object.values(config.servers);
  }

  async saveServer(server: ServerConfig): Promise<void> {
    const config = this.store.store;
    config.servers[server.name] = server;
    this.store.store = config;
  }

  async deleteServer(name: string): Promise<void> {
    if (name === "local") {
      throw new Error("Cannot delete local server");
    }

    const config = this.store.store;

    if (config.activeServer === name) {
      config.activeServer = "local";
    }

    delete config.servers[name];
    this.store.store = config;
  }

  async setActiveServer(name: string): Promise<void> {
    const config = this.store.store;

    if (!config.servers[name]) {
      throw new Error(`Server not found: ${name}`);
    }

    config.activeServer = name;
    this.store.store = config;
  }

  /**
   * Get the configuration file path
   */
  getConfigPath(): string {
    return this.store.path;
  }
}
