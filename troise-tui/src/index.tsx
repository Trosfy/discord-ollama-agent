#!/usr/bin/env bun
/**
 * TROISE TUI - Terminal UI for TROISE AI
 *
 * A performant, feature-rich terminal interface for interacting with
 * TROISE AI personal assistant.
 */
import { render } from "ink";
import { program } from "commander";
import { App } from "./presentation/components/App";
import { StateProvider } from "./presentation/context/StateProvider";
import { LocalConfigStore } from "./adapters/storage/LocalConfigStore";

// Clear screen helper
function clearScreen() {
  process.stdout.write("\x1b[2J\x1b[H");
}

// Parse CLI arguments
program
  .name("troise")
  .description("Terminal UI for TROISE AI")
  .version("0.1.0")
  .option("-s, --server <url>", "Server URL or profile name")
  .option("-p, --profile <name>", "Configuration profile to use")
  .option("-d, --directory <path>", "Working directory")
  .option("--no-color", "Disable colors")
  .option("--debug", "Enable debug mode")
  .parse();

const options = program.opts();

async function main() {
  // Load configuration
  const configStore = new LocalConfigStore();
  const config = await configStore.getConfig();

  // Determine server URL
  let serverUrl = config.servers[config.activeServer]?.url || "ws://localhost:8001";

  if (options.server) {
    // Check if it's a server profile name or URL
    const serverConfig = config.servers[options.server];
    if (serverConfig) {
      serverUrl = serverConfig.url;
    } else if (options.server.startsWith("ws://") || options.server.startsWith("wss://")) {
      serverUrl = options.server;
    }
  }

  // Determine profile
  let profileName = options.profile || config.activeProfile;
  const profile = config.profiles[profileName] || config.profiles.default;

  // Working directory
  const workingDir = options.directory || profile.execution.workingDir || process.cwd();

  // Generate user ID
  const userId = `cli-${process.env.USER || "user"}`;

  // Debug info
  if (options.debug) {
    console.log("Configuration:");
    console.log(`  Server: ${serverUrl}`);
    console.log(`  Profile: ${profileName}`);
    console.log(`  Working Dir: ${workingDir}`);
    console.log(`  User ID: ${userId}`);
    console.log(`  Config Path: ${configStore.getConfigPath()}`);
    console.log("");
  }

  // Clear screen before rendering
  clearScreen();

  // Hide cursor during app
  process.stdout.write("\x1b[?25l");

  // Render the app without fullScreen (we handle clearing manually)
  const { waitUntilExit } = render(
    <StateProvider
      serverUrl={serverUrl}
      userId={userId}
      profile={profile}
      workingDir={workingDir}
    >
      <App />
    </StateProvider>
  );

  // Wait for exit
  await waitUntilExit();

  // Show cursor and clear screen on exit
  process.stdout.write("\x1b[?25h");
  clearScreen();
}

// Handle errors
main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
