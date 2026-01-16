import type { AppState } from "./AppState";
import type { AppAction } from "./actions";
import { createAssistantMessage } from "@domain/entities";

/**
 * Root reducer for application state
 */
export function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    // =========================================================================
    // Connection
    // =========================================================================
    case "CONNECTION_STATUS_CHANGED":
      return {
        ...state,
        connection: {
          ...state.connection,
          status: action.status,
          lastError: action.error,
          connectedAt: action.status === "connected" ? new Date() : state.connection.connectedAt,
        },
      };

    case "SESSION_STARTED":
      return {
        ...state,
        connection: {
          ...state.connection,
          sessionId: action.sessionId,
          userId: action.userId,
        },
      };

    case "RETRY_INCREMENT":
      return {
        ...state,
        connection: {
          ...state.connection,
          retryCount: state.connection.retryCount + 1,
        },
      };

    case "RETRY_RESET":
      return {
        ...state,
        connection: {
          ...state.connection,
          retryCount: 0,
        },
      };

    // =========================================================================
    // Chat
    // =========================================================================
    case "MESSAGE_ADDED":
      return {
        ...state,
        chat: {
          ...state.chat,
          messages: [...state.chat.messages, action.message],
          error: null,
        },
      };

    case "MESSAGES_LOADED":
      return {
        ...state,
        chat: {
          ...state.chat,
          messages: action.messages,
        },
      };

    case "STREAMING_STARTED":
      return {
        ...state,
        chat: {
          ...state.chat,
          isStreaming: true,
          streamingContent: "",
          streamingRequestId: action.requestId,
        },
      };

    case "STREAMING_CHUNK":
      return {
        ...state,
        chat: {
          ...state.chat,
          streamingContent: state.chat.streamingContent + action.content,
        },
      };

    case "STREAMING_ENDED": {
      // Convert streaming content to a message
      const streamingMessage = createAssistantMessage(state.chat.streamingContent, {
        isStreaming: false,
        requestId: state.chat.streamingRequestId || undefined,
      });

      return {
        ...state,
        chat: {
          ...state.chat,
          isStreaming: false,
          streamingContent: "",
          streamingRequestId: null,
          messages: state.chat.streamingContent
            ? [...state.chat.messages, streamingMessage]
            : state.chat.messages,
        },
      };
    }

    case "QUESTION_RECEIVED":
      return {
        ...state,
        chat: {
          ...state.chat,
          pendingQuestion: action.question,
        },
      };

    case "QUESTION_ANSWERED":
      return {
        ...state,
        chat: {
          ...state.chat,
          pendingQuestion: null,
        },
      };

    case "INPUT_QUEUED":
      return {
        ...state,
        chat: {
          ...state.chat,
          inputQueue: [...state.chat.inputQueue, action.input],
        },
      };

    case "INPUT_DEQUEUED":
      return {
        ...state,
        chat: {
          ...state.chat,
          inputQueue: state.chat.inputQueue.filter((i) => i.id !== action.id),
        },
      };

    case "CHAT_ERROR":
      return {
        ...state,
        chat: {
          ...state.chat,
          error: action.error,
          isStreaming: false,
        },
      };

    case "CHAT_ERROR_CLEARED":
      return {
        ...state,
        chat: {
          ...state.chat,
          error: null,
        },
      };

    // =========================================================================
    // Session
    // =========================================================================
    case "SESSION_LOADED":
      return {
        ...state,
        session: {
          ...state.session,
          current: action.session,
          loading: false,
        },
      };

    case "SESSION_UPDATED":
      return {
        ...state,
        session: {
          ...state.session,
          current: state.session.current
            ? { ...state.session.current, ...action.updates }
            : null,
        },
      };

    case "SESSION_HISTORY_LOADED":
      return {
        ...state,
        session: {
          ...state.session,
          history: action.sessions,
          loading: false,
        },
      };

    case "SESSION_LOADING":
      return {
        ...state,
        session: {
          ...state.session,
          loading: action.loading,
        },
      };

    // =========================================================================
    // Files
    // =========================================================================
    case "FILES_PATH_CHANGED":
      return {
        ...state,
        files: {
          ...state.files,
          currentPath: action.path,
          selectedEntry: null,
          fileContent: null,
        },
      };

    case "FILES_LOADED":
      return {
        ...state,
        files: {
          ...state.files,
          entries: action.entries,
          isLoading: false,
          error: null,
        },
      };

    case "FILE_SELECTED":
      return {
        ...state,
        files: {
          ...state.files,
          selectedEntry: action.entry,
        },
      };

    case "FILE_CONTENT_LOADED":
      return {
        ...state,
        files: {
          ...state.files,
          fileContent: action.content,
        },
      };

    case "FILE_CONTENT_CLEARED":
      return {
        ...state,
        files: {
          ...state.files,
          fileContent: null,
        },
      };

    case "DIRECTORY_TOGGLED": {
      const newExpanded = new Set(state.files.expandedPaths);
      if (newExpanded.has(action.path)) {
        newExpanded.delete(action.path);
      } else {
        newExpanded.add(action.path);
      }
      return {
        ...state,
        files: {
          ...state.files,
          expandedPaths: newExpanded,
        },
      };
    }

    case "FILES_LOADING":
      return {
        ...state,
        files: {
          ...state.files,
          isLoading: action.loading,
        },
      };

    case "FILES_ERROR":
      return {
        ...state,
        files: {
          ...state.files,
          error: action.error,
          isLoading: false,
        },
      };

    // =========================================================================
    // Shell
    // =========================================================================
    case "COMMAND_STARTED":
      return {
        ...state,
        shell: {
          ...state.shell,
          commands: [...state.shell.commands, action.command],
          currentCommand: action.command,
        },
      };

    case "COMMAND_OUTPUT": {
      const commands = state.shell.commands.map((cmd) =>
        cmd.id === action.commandId
          ? {
              ...cmd,
              stdout: cmd.stdout + (action.stdout || ""),
              stderr: cmd.stderr + (action.stderr || ""),
            }
          : cmd
      );
      return {
        ...state,
        shell: {
          ...state.shell,
          commands,
          currentCommand:
            state.shell.currentCommand?.id === action.commandId
              ? commands.find((c) => c.id === action.commandId) || null
              : state.shell.currentCommand,
        },
      };
    }

    case "COMMAND_COMPLETED": {
      const commands = state.shell.commands.map((cmd) =>
        cmd.id === action.commandId
          ? {
              ...cmd,
              status: action.exitCode === 0 ? "completed" : "failed",
              exitCode: action.exitCode,
              completedAt: new Date(),
            } as const
          : cmd
      );
      return {
        ...state,
        shell: {
          ...state.shell,
          commands,
          currentCommand:
            state.shell.currentCommand?.id === action.commandId
              ? null
              : state.shell.currentCommand,
        },
      };
    }

    case "COMMAND_CANCELLED": {
      const commands = state.shell.commands.map((cmd) =>
        cmd.id === action.commandId
          ? { ...cmd, status: "cancelled" as const, completedAt: new Date() }
          : cmd
      );
      return {
        ...state,
        shell: {
          ...state.shell,
          commands,
          currentCommand:
            state.shell.currentCommand?.id === action.commandId
              ? null
              : state.shell.currentCommand,
        },
      };
    }

    case "SHELL_HISTORY_ADDED":
      return {
        ...state,
        shell: {
          ...state.shell,
          history: [...state.shell.history, action.command],
          historyIndex: -1,
        },
      };

    case "SHELL_HISTORY_INDEX_CHANGED":
      return {
        ...state,
        shell: {
          ...state.shell,
          historyIndex: action.index,
        },
      };

    case "SHELL_WORKING_DIR_CHANGED":
      return {
        ...state,
        shell: {
          ...state.shell,
          workingDir: action.path,
        },
      };

    // =========================================================================
    // UI
    // =========================================================================
    case "TAB_CHANGED":
      return {
        ...state,
        ui: {
          ...state.ui,
          activeTab: action.tab,
        },
      };

    case "THEME_CHANGED":
      return {
        ...state,
        ui: {
          ...state.ui,
          theme: action.theme,
        },
      };

    case "SPLIT_VIEW_TOGGLED":
      return {
        ...state,
        ui: {
          ...state.ui,
          splitView: {
            ...state.ui.splitView,
            enabled: !state.ui.splitView.enabled,
          },
        },
      };

    case "SPLIT_VIEW_LAYOUT_CHANGED":
      return {
        ...state,
        ui: {
          ...state.ui,
          splitView: {
            ...state.ui.splitView,
            layout: action.layout,
          },
        },
      };

    case "SPLIT_VIEW_RATIO_CHANGED":
      return {
        ...state,
        ui: {
          ...state.ui,
          splitView: {
            ...state.ui.splitView,
            ratio: Math.max(20, Math.min(80, action.ratio)),
          },
        },
      };

    case "SPLIT_VIEW_PANELS_CHANGED":
      return {
        ...state,
        ui: {
          ...state.ui,
          splitView: {
            ...state.ui.splitView,
            leftPanel: action.left,
            rightPanel: action.right,
          },
        },
      };

    case "NOTIFICATION_ADDED":
      return {
        ...state,
        ui: {
          ...state.ui,
          notifications: [...state.ui.notifications, action.notification],
        },
      };

    case "NOTIFICATION_REMOVED":
      return {
        ...state,
        ui: {
          ...state.ui,
          notifications: state.ui.notifications.filter((n) => n.id !== action.id),
        },
      };

    case "CONFIRM_DIALOG_OPENED":
      return {
        ...state,
        ui: {
          ...state.ui,
          modals: {
            ...state.ui.modals,
            confirmDialog: action.dialog,
          },
        },
      };

    case "CONFIRM_DIALOG_CLOSED":
      return {
        ...state,
        ui: {
          ...state.ui,
          modals: {
            ...state.ui.modals,
            confirmDialog: null,
          },
        },
      };

    case "COMMAND_APPROVAL_OPENED":
      return {
        ...state,
        ui: {
          ...state.ui,
          modals: {
            ...state.ui.modals,
            commandApproval: action.approval,
          },
        },
      };

    case "COMMAND_APPROVAL_CLOSED":
      return {
        ...state,
        ui: {
          ...state.ui,
          modals: {
            ...state.ui.modals,
            commandApproval: null,
          },
        },
      };

    case "LOADING_SET":
      return {
        ...state,
        ui: {
          ...state.ui,
          loading: {
            ...state.ui.loading,
            messages: {
              ...state.ui.loading.messages,
              [action.key]: action.loading,
            },
          },
        },
      };

    // =========================================================================
    // Config
    // =========================================================================
    case "PROFILE_LOADED":
      return {
        ...state,
        config: {
          ...state.config,
          activeProfile: action.profile,
        },
      };

    case "PROFILES_LOADED":
      return {
        ...state,
        config: {
          ...state.config,
          profiles: action.profiles,
        },
      };

    case "SERVER_LOADED":
      return {
        ...state,
        config: {
          ...state.config,
          activeServer: action.server,
        },
        connection: {
          ...state.connection,
          serverUrl: action.server.url,
        },
      };

    case "SERVERS_LOADED":
      return {
        ...state,
        config: {
          ...state.config,
          servers: action.servers,
        },
      };

    default:
      return state;
  }
}
