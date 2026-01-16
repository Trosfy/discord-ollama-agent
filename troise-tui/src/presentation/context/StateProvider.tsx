import React, { createContext, useContext, useReducer, useEffect, type ReactNode } from "react";
import type { AppState, AppAction } from "@application/state";
import { createInitialState, appReducer } from "@application/state";
import type { Profile } from "@application/ports";
import { TroiseWebSocketClient } from "@adapters/websocket/TroiseWebSocketClient";
import { BunFileSystem } from "@adapters/filesystem/BunFileSystem";
import { BunCommandExecutor } from "@adapters/shell/BunCommandExecutor";
import { LocalConfigStore } from "@adapters/storage/LocalConfigStore";
import { createTheme } from "@domain/value-objects";
import { actions } from "@application/state/actions";

// Services context
interface Services {
  wsClient: TroiseWebSocketClient;
  fileSystem: BunFileSystem;
  commandExecutor: BunCommandExecutor;
  configStore: LocalConfigStore;
}

const ServicesContext = createContext<Services | null>(null);
const StateContext = createContext<AppState | null>(null);
const DispatchContext = createContext<React.Dispatch<AppAction> | null>(null);

interface StateProviderProps {
  children: ReactNode;
  serverUrl: string;
  userId: string;
  profile: Profile;
  workingDir: string;
}

export function StateProvider({
  children,
  serverUrl,
  userId,
  profile,
  workingDir,
}: StateProviderProps) {
  // Create initial state with config
  const initialState = createInitialState();
  initialState.connection.serverUrl = serverUrl;
  initialState.config.activeProfile = profile;
  initialState.files.currentPath = workingDir;
  initialState.shell.workingDir = workingDir;

  // Detect theme
  const detectedTheme = detectTerminalTheme();
  initialState.ui.theme = createTheme(profile.ui.theme, detectedTheme);
  initialState.ui.splitView = {
    ...initialState.ui.splitView,
    ...profile.ui.splitView,
  };

  const [state, dispatch] = useReducer(appReducer, initialState);

  // Create services (singleton)
  const services = React.useMemo<Services>(
    () => ({
      wsClient: new TroiseWebSocketClient(),
      fileSystem: new BunFileSystem(),
      commandExecutor: new BunCommandExecutor(),
      configStore: new LocalConfigStore(),
    }),
    []
  );

  // Connect to WebSocket on mount
  useEffect(() => {
    const { wsClient } = services;

    // Register event handlers
    wsClient.on("connected", (data) => {
      dispatch(actions.connectionStatusChanged("connected"));
      dispatch(actions.sessionStarted(data.sessionId, data.userId, data.resumed));
    });

    wsClient.on("disconnected", (reason) => {
      dispatch(actions.connectionStatusChanged("disconnected", reason));
    });

    // Track current streaming request to avoid resetting on every chunk
    let currentStreamingRequestId: string | null = null;

    wsClient.on("stream", (data) => {
      // Only start streaming once per request
      if (data.requestId && data.requestId !== currentStreamingRequestId) {
        currentStreamingRequestId = data.requestId;
        dispatch(actions.streamingStarted(data.requestId));
      }
      if (data.content) {
        dispatch(actions.streamingChunk(data.content));
      }
    });

    wsClient.on("streamEnd", () => {
      currentStreamingRequestId = null;
      dispatch(actions.streamingEnded());
    });

    wsClient.on("response", (data) => {
      if (process.env.DEBUG_WS) {
        console.log(`[Response] content: "${data.content?.slice(0, 100)}", source: ${JSON.stringify(data.source)}`);
      }
      if (data.content) {
        dispatch(
          actions.messageAdded({
            id: crypto.randomUUID(),
            role: "assistant",
            content: data.content,
            timestamp: new Date(),
            metadata: {
              source: data.source,
            },
          })
        );
      }
    });

    wsClient.on("question", (data) => {
      dispatch(
        actions.questionReceived({
          requestId: data.requestId,
          question: data.question,
          options: data.options,
        })
      );
    });

    wsClient.on("error", (data) => {
      dispatch({ type: "CHAT_ERROR", error: data.error });
      dispatch(
        actions.notificationAdded("error", "Error", data.error, true, 5000)
      );
    });

    wsClient.on("executeCommand", async (data) => {
      // Agent wants to execute a command
      if (data.requiresApproval) {
        dispatch(
          actions.commandApprovalOpened({
            command: data.command,
            requestId: data.requestId,
            onApprove: async () => {
              dispatch({ type: "COMMAND_APPROVAL_CLOSED" });
              await executeAgentCommand(data.command, data.requestId, data.workingDir);
            },
            onReject: async () => {
              dispatch({ type: "COMMAND_APPROVAL_CLOSED" });
              await wsClient.sendCommandOutput(
                data.requestId,
                "",
                "Command rejected by user",
                1,
                "cancelled"
              );
            },
          })
        );
      } else {
        await executeAgentCommand(data.command, data.requestId, data.workingDir);
      }
    });

    // Helper to execute agent commands
    const executeAgentCommand = async (
      command: string,
      requestId: string,
      workingDir?: string
    ) => {
      const { commandExecutor } = services;
      try {
        const result = await commandExecutor.execute(command, {
          cwd: workingDir || state.shell.workingDir,
          commandId: requestId,
        });
        await wsClient.sendCommandOutput(
          requestId,
          result.stdout,
          result.stderr,
          result.exitCode,
          "completed"
        );
      } catch (error) {
        await wsClient.sendCommandOutput(
          requestId,
          "",
          String(error),
          1,
          "error"
        );
      }
    };

    // Connect
    dispatch(actions.connectionStatusChanged("connecting"));
    wsClient.connect(serverUrl, userId).catch((error) => {
      dispatch(actions.connectionStatusChanged("error", String(error)));
    });

    // Cleanup on unmount
    return () => {
      wsClient.disconnect();
    };
  }, [serverUrl, userId]);

  return (
    <ServicesContext.Provider value={services}>
      <StateContext.Provider value={state}>
        <DispatchContext.Provider value={dispatch}>
          {children}
        </DispatchContext.Provider>
      </StateContext.Provider>
    </ServicesContext.Provider>
  );
}

// Hooks
export function useServices(): Services {
  const services = useContext(ServicesContext);
  if (!services) {
    throw new Error("useServices must be used within StateProvider");
  }
  return services;
}

export function useAppState(): AppState {
  const state = useContext(StateContext);
  if (!state) {
    throw new Error("useAppState must be used within StateProvider");
  }
  return state;
}

export function useDispatch(): React.Dispatch<AppAction> {
  const dispatch = useContext(DispatchContext);
  if (!dispatch) {
    throw new Error("useDispatch must be used within StateProvider");
  }
  return dispatch;
}

// Theme detection helper
function detectTerminalTheme(): "dark" | "light" {
  // Check COLORFGBG environment variable (common in many terminals)
  const colorFgBg = process.env.COLORFGBG;
  if (colorFgBg) {
    const parts = colorFgBg.split(";");
    const bg = parseInt(parts[parts.length - 1], 10);
    if (!isNaN(bg)) {
      // Background color index: 0-7 are dark, 8-15 are light
      return bg < 8 ? "dark" : "light";
    }
  }

  // Check terminal program hints
  const termProgram = process.env.TERM_PROGRAM?.toLowerCase();
  if (termProgram?.includes("apple_terminal")) {
    return "light"; // Apple Terminal defaults to light
  }

  // Default to dark (most common for developers)
  return "dark";
}
