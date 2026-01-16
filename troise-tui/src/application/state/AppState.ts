import type { Message, Session, Command, FileEntry } from "@domain/entities";
import type { TabType, ConnectionState, Theme } from "@domain/value-objects";
import type { Profile, ServerConfig, UIConfig } from "@application/ports";

/**
 * Root application state
 */
export interface AppState {
  // Connection
  connection: ConnectionState;

  // Session
  session: SessionState;

  // Chat
  chat: ChatState;

  // Files
  files: FilesState;

  // Shell
  shell: ShellState;

  // UI
  ui: UIState;

  // Config
  config: ConfigState;
}

export interface SessionState {
  current: Session | null;
  history: Session[];
  loading: boolean;
}

export interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  streamingContent: string;
  streamingRequestId: string | null;
  pendingQuestion: PendingQuestion | null;
  inputQueue: QueuedInput[];
  error: string | null;
}

export interface PendingQuestion {
  requestId: string;
  question: string;
  options?: string[];
}

export interface QueuedInput {
  id: string;
  content: string;
  timestamp: Date;
}

export interface FilesState {
  currentPath: string;
  entries: FileEntry[];
  selectedEntry: FileEntry | null;
  expandedPaths: Set<string>;
  fileContent: string | null;
  isLoading: boolean;
  error: string | null;
}

export interface ShellState {
  commands: Command[];
  currentCommand: Command | null;
  history: string[];
  historyIndex: number;
  workingDir: string;
}

export interface UIState {
  activeTab: TabType;
  theme: Theme;
  splitView: SplitViewState;
  notifications: Notification[];
  modals: ModalState;
  loading: LoadingState;
}

export interface SplitViewState {
  enabled: boolean;
  layout: "horizontal" | "vertical";
  ratio: number;
  leftPanel: TabType;
  rightPanel: TabType;
}

export interface Notification {
  id: string;
  type: "success" | "warning" | "error" | "info";
  title: string;
  message?: string;
  autoDismiss: boolean;
  duration: number;
  timestamp: Date;
}

export interface ModalState {
  confirmDialog: ConfirmDialogState | null;
  commandApproval: CommandApprovalState | null;
}

export interface ConfirmDialogState {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export interface CommandApprovalState {
  command: string;
  requestId: string;
  onApprove: () => void;
  onReject: () => void;
}

export interface LoadingState {
  global: boolean;
  messages: Record<string, boolean>;
}

export interface ConfigState {
  activeProfile: Profile | null;
  activeServer: ServerConfig | null;
  profiles: Profile[];
  servers: ServerConfig[];
}

/**
 * Create initial application state
 */
export function createInitialState(): AppState {
  return {
    connection: {
      status: "disconnected",
      serverUrl: "ws://localhost:8001",
      retryCount: 0,
    },
    session: {
      current: null,
      history: [],
      loading: false,
    },
    chat: {
      messages: [],
      isStreaming: false,
      streamingContent: "",
      streamingRequestId: null,
      pendingQuestion: null,
      inputQueue: [],
      error: null,
    },
    files: {
      currentPath: process.cwd(),
      entries: [],
      selectedEntry: null,
      expandedPaths: new Set(),
      fileContent: null,
      isLoading: false,
      error: null,
    },
    shell: {
      commands: [],
      currentCommand: null,
      history: [],
      historyIndex: -1,
      workingDir: process.cwd(),
    },
    ui: {
      activeTab: "chat",
      theme: {
        mode: "auto",
        colors: {} as any, // Will be populated on init
      },
      splitView: {
        enabled: false,
        layout: "horizontal",
        ratio: 50,
        leftPanel: "chat",
        rightPanel: "files",
      },
      notifications: [],
      modals: {
        confirmDialog: null,
        commandApproval: null,
      },
      loading: {
        global: false,
        messages: {},
      },
    },
    config: {
      activeProfile: null,
      activeServer: null,
      profiles: [],
      servers: [],
    },
  };
}
