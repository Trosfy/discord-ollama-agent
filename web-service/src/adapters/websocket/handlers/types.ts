/**
 * WebSocket Message Handler Types
 *
 * Defines the handler pattern for processing WebSocket messages.
 * Follows OCP - add new handlers without modifying existing code.
 */

import type { IncomingFile, FileSuggestion } from "@/core/types/file.types";
import type { HistoryMessage } from "@/infrastructure/websocket/ChatWebSocket";

/**
 * Base WebSocket message structure
 */
export interface WebSocketMessage {
  type: string;
  [key: string]: unknown;
}

/**
 * Handler context - provides access to callbacks and state
 */
export interface HandlerContext {
  callbacks: MessageCallbacks;
}

/**
 * Callback interface for message handlers
 */
export interface MessageCallbacks {
  // Streaming
  onToken?: (token: string) => void;
  onDone?: (tokensUsed?: number, generationTime?: number, outputTokens?: number, totalTokensGenerated?: number, model?: string) => void;

  // Connection
  onConnect?: () => void;
  onDisconnect?: () => void;
  onSessionStart?: (sessionId: string) => void;

  // Routing & Queue
  onRouting?: (skillOrAgent: string, routingType: string, reason?: string) => void;
  onQueued?: (requestId: string, position?: number) => void;

  // Interactive
  onQuestion?: (question: string, options?: string[], requestId?: string) => void;
  onWarning?: (warning: string) => void;

  // Files
  onFile?: (file: IncomingFile) => void;
  onFileSuggestion?: (file: FileSuggestion) => void;

  // Control
  onError?: (error: string, availableModels?: Array<{ name: string; supports_thinking?: boolean }>) => void;
  onCancelled?: (requestId?: string, reason?: string) => void;

  // History
  onHistory?: (messages: HistoryMessage[]) => void;
  onCloseComplete?: (deletedCount: number) => void;
}

/**
 * Message handler interface (OCP)
 * Each handler processes one message type
 */
export interface IMessageHandler<T extends WebSocketMessage = WebSocketMessage> {
  /**
   * The message type this handler processes
   */
  readonly messageType: string;

  /**
   * Process the message
   * @param message - The WebSocket message
   * @param context - Handler context with callbacks
   */
  handle(message: T, context: HandlerContext): void;
}
