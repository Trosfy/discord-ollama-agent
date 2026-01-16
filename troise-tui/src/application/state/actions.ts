import type {
  Message,
  Session,
  Command,
  FileEntry,
  FileAttachment,
} from "@domain/entities";
import type { TabType, ConnectionStatus, Theme } from "@domain/value-objects";
import type { Profile, ServerConfig } from "@application/ports";
import type {
  AppState,
  PendingQuestion,
  QueuedInput,
  Notification,
  ConfirmDialogState,
  CommandApprovalState,
} from "./AppState";

/**
 * Action types for state mutations
 */
export type AppAction =
  // Connection actions
  | { type: "CONNECTION_STATUS_CHANGED"; status: ConnectionStatus; error?: string }
  | { type: "SESSION_STARTED"; sessionId: string; userId: string; resumed: boolean }
  | { type: "RETRY_INCREMENT" }
  | { type: "RETRY_RESET" }

  // Chat actions
  | { type: "MESSAGE_ADDED"; message: Message }
  | { type: "STREAMING_STARTED"; requestId: string }
  | { type: "STREAMING_CHUNK"; content: string }
  | { type: "STREAMING_ENDED" }
  | { type: "QUESTION_RECEIVED"; question: PendingQuestion }
  | { type: "QUESTION_ANSWERED" }
  | { type: "INPUT_QUEUED"; input: QueuedInput }
  | { type: "INPUT_DEQUEUED"; id: string }
  | { type: "CHAT_ERROR"; error: string }
  | { type: "CHAT_ERROR_CLEARED" }
  | { type: "MESSAGES_LOADED"; messages: Message[] }

  // Session actions
  | { type: "SESSION_LOADED"; session: Session }
  | { type: "SESSION_UPDATED"; updates: Partial<Session> }
  | { type: "SESSION_HISTORY_LOADED"; sessions: Session[] }
  | { type: "SESSION_LOADING"; loading: boolean }

  // Files actions
  | { type: "FILES_PATH_CHANGED"; path: string }
  | { type: "FILES_LOADED"; entries: FileEntry[] }
  | { type: "FILE_SELECTED"; entry: FileEntry | null }
  | { type: "FILE_CONTENT_LOADED"; content: string }
  | { type: "FILE_CONTENT_CLEARED" }
  | { type: "DIRECTORY_TOGGLED"; path: string }
  | { type: "FILES_LOADING"; loading: boolean }
  | { type: "FILES_ERROR"; error: string }

  // Shell actions
  | { type: "COMMAND_STARTED"; command: Command }
  | { type: "COMMAND_OUTPUT"; commandId: string; stdout?: string; stderr?: string }
  | { type: "COMMAND_COMPLETED"; commandId: string; exitCode: number }
  | { type: "COMMAND_CANCELLED"; commandId: string }
  | { type: "SHELL_HISTORY_ADDED"; command: string }
  | { type: "SHELL_HISTORY_INDEX_CHANGED"; index: number }
  | { type: "SHELL_WORKING_DIR_CHANGED"; path: string }

  // UI actions
  | { type: "TAB_CHANGED"; tab: TabType }
  | { type: "THEME_CHANGED"; theme: Theme }
  | { type: "SPLIT_VIEW_TOGGLED" }
  | { type: "SPLIT_VIEW_LAYOUT_CHANGED"; layout: "horizontal" | "vertical" }
  | { type: "SPLIT_VIEW_RATIO_CHANGED"; ratio: number }
  | { type: "SPLIT_VIEW_PANELS_CHANGED"; left: TabType; right: TabType }
  | { type: "NOTIFICATION_ADDED"; notification: Notification }
  | { type: "NOTIFICATION_REMOVED"; id: string }
  | { type: "CONFIRM_DIALOG_OPENED"; dialog: ConfirmDialogState }
  | { type: "CONFIRM_DIALOG_CLOSED" }
  | { type: "COMMAND_APPROVAL_OPENED"; approval: CommandApprovalState }
  | { type: "COMMAND_APPROVAL_CLOSED" }
  | { type: "LOADING_SET"; key: string; loading: boolean }

  // Config actions
  | { type: "PROFILE_LOADED"; profile: Profile }
  | { type: "PROFILES_LOADED"; profiles: Profile[] }
  | { type: "SERVER_LOADED"; server: ServerConfig }
  | { type: "SERVERS_LOADED"; servers: ServerConfig[] };

/**
 * Action creators
 */
export const actions = {
  // Connection
  connectionStatusChanged: (status: ConnectionStatus, error?: string): AppAction => ({
    type: "CONNECTION_STATUS_CHANGED",
    status,
    error,
  }),

  sessionStarted: (sessionId: string, userId: string, resumed: boolean): AppAction => ({
    type: "SESSION_STARTED",
    sessionId,
    userId,
    resumed,
  }),

  // Chat
  messageAdded: (message: Message): AppAction => ({
    type: "MESSAGE_ADDED",
    message,
  }),

  streamingStarted: (requestId: string): AppAction => ({
    type: "STREAMING_STARTED",
    requestId,
  }),

  streamingChunk: (content: string): AppAction => ({
    type: "STREAMING_CHUNK",
    content,
  }),

  streamingEnded: (): AppAction => ({
    type: "STREAMING_ENDED",
  }),

  questionReceived: (question: PendingQuestion): AppAction => ({
    type: "QUESTION_RECEIVED",
    question,
  }),

  inputQueued: (content: string): AppAction => ({
    type: "INPUT_QUEUED",
    input: {
      id: crypto.randomUUID(),
      content,
      timestamp: new Date(),
    },
  }),

  // Files
  filesPathChanged: (path: string): AppAction => ({
    type: "FILES_PATH_CHANGED",
    path,
  }),

  filesLoaded: (entries: FileEntry[]): AppAction => ({
    type: "FILES_LOADED",
    entries,
  }),

  fileSelected: (entry: FileEntry | null): AppAction => ({
    type: "FILE_SELECTED",
    entry,
  }),

  // Shell
  commandStarted: (command: Command): AppAction => ({
    type: "COMMAND_STARTED",
    command,
  }),

  commandOutput: (commandId: string, stdout?: string, stderr?: string): AppAction => ({
    type: "COMMAND_OUTPUT",
    commandId,
    stdout,
    stderr,
  }),

  commandCompleted: (commandId: string, exitCode: number): AppAction => ({
    type: "COMMAND_COMPLETED",
    commandId,
    exitCode,
  }),

  // UI
  tabChanged: (tab: TabType): AppAction => ({
    type: "TAB_CHANGED",
    tab,
  }),

  notificationAdded: (
    type: Notification["type"],
    title: string,
    message?: string,
    autoDismiss = true,
    duration = 3000
  ): AppAction => ({
    type: "NOTIFICATION_ADDED",
    notification: {
      id: crypto.randomUUID(),
      type,
      title,
      message,
      autoDismiss,
      duration,
      timestamp: new Date(),
    },
  }),

  notificationRemoved: (id: string): AppAction => ({
    type: "NOTIFICATION_REMOVED",
    id,
  }),

  confirmDialogOpened: (dialog: ConfirmDialogState): AppAction => ({
    type: "CONFIRM_DIALOG_OPENED",
    dialog,
  }),

  commandApprovalOpened: (approval: CommandApprovalState): AppAction => ({
    type: "COMMAND_APPROVAL_OPENED",
    approval,
  }),

  // Config
  profileLoaded: (profile: Profile): AppAction => ({
    type: "PROFILE_LOADED",
    profile,
  }),

  serverLoaded: (server: ServerConfig): AppAction => ({
    type: "SERVER_LOADED",
    server,
  }),
};
