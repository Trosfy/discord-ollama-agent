import type { FileAttachment, Message } from "@domain/entities";

/**
 * WebSocket client interface for TROISE AI communication.
 */
export interface IWebSocketClient {
  /**
   * Connect to TROISE AI server
   */
  connect(url: string, userId: string): Promise<void>;

  /**
   * Disconnect from server
   */
  disconnect(): Promise<void>;

  /**
   * Send a chat message
   */
  sendMessage(
    content: string,
    options?: SendMessageOptions
  ): Promise<void>;

  /**
   * Send answer to agent question
   */
  sendAnswer(requestId: string, answer: string): Promise<void>;

  /**
   * Cancel a pending request
   */
  cancelRequest(requestId: string): Promise<void>;

  /**
   * Request conversation history
   */
  requestHistory(): Promise<void>;

  /**
   * Check if connected
   */
  isConnected(): boolean;

  /**
   * Get current session ID
   */
  getSessionId(): string | undefined;

  /**
   * Register event handlers
   */
  on<K extends keyof WebSocketEvents>(
    event: K,
    handler: WebSocketEvents[K]
  ): void;

  /**
   * Remove event handler
   */
  off<K extends keyof WebSocketEvents>(
    event: K,
    handler: WebSocketEvents[K]
  ): void;
}

export interface SendMessageOptions {
  /** Files to attach */
  files?: FileAttachment[];
  /** Message ID for idempotency */
  messageId?: string;
  /** Additional metadata */
  metadata?: Record<string, unknown>;
}

/**
 * WebSocket event handlers
 */
export interface WebSocketEvents {
  /** Connection established */
  connected: (data: SessionStartEvent) => void;
  /** Connection lost */
  disconnected: (reason?: string) => void;
  /** Routing decision */
  routing: (data: RoutingEvent) => void;
  /** Request queued */
  queued: (data: QueuedEvent) => void;
  /** Streaming content chunk */
  stream: (data: StreamEvent) => void;
  /** Streaming complete */
  streamEnd: (data: StreamEndEvent) => void;
  /** Complete response */
  response: (data: ResponseEvent) => void;
  /** Agent question */
  question: (data: QuestionEvent) => void;
  /** File artifact */
  file: (data: FileEvent) => void;
  /** Execute command (from agent) */
  executeCommand: (data: ExecuteCommandEvent) => void;
  /** Error */
  error: (data: ErrorEvent) => void;
  /** History loaded */
  history: (data: HistoryEvent) => void;
  /** Request cancelled */
  cancelled: (data: CancelledEvent) => void;
}

// Event data types
export interface SessionStartEvent {
  sessionId: string;
  userId: string;
  interface: string;
  resumed: boolean;
  messageCount?: number;
}

export interface RoutingEvent {
  skillOrAgent: string;
  routingType: "skill" | "agent";
  reason?: string;
}

export interface QueuedEvent {
  requestId: string;
  position: number;
}

export interface StreamEvent {
  content: string;
  requestId?: string;
}

export interface StreamEndEvent {
  requestId?: string;
}

export interface ResponseEvent {
  content: string;
  source?: {
    type: "skill" | "agent";
    name: string;
  };
  part?: number;
  totalParts?: number;
}

export interface QuestionEvent {
  requestId: string;
  question: string;
  options?: string[];
}

export interface FileEvent {
  filename: string;
  base64Data: string;
  mimetype: string;
  confidence?: number;
}

export interface ExecuteCommandEvent {
  requestId: string;
  command: string;
  workingDir?: string;
  requiresApproval: boolean;
}

export interface ErrorEvent {
  error: string;
  code?: string;
}

export interface HistoryEvent {
  sessionId: string;
  messages: Array<{
    role: string;
    content: string;
    timestamp?: string;
  }>;
}

export interface CancelledEvent {
  requestId: string;
  reason?: string;
}
