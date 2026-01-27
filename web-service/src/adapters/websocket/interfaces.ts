/**
 * WebSocket Callback Interfaces (ISP)
 *
 * Segregated interfaces for WebSocket callbacks.
 * Clients implement only what they need.
 */

import type { IncomingFile, FileSuggestion } from "@/core/types/file.types";
import type { HistoryMessage } from "@/infrastructure/websocket/ChatWebSocket";

/**
 * Text streaming callbacks
 */
export interface ITextStreamCallbacks {
  onToken?: (token: string) => void;
  onDone?: (tokensUsed?: number, generationTime?: number, outputTokens?: number, totalTokensGenerated?: number, model?: string) => void;
}

/**
 * Connection lifecycle callbacks
 */
export interface IConnectionCallbacks {
  onConnect?: () => void;
  onDisconnect?: () => void;
  onSessionStart?: (sessionId: string) => void;
}

/**
 * Routing and queue callbacks
 */
export interface IRoutingCallbacks {
  onRouting?: (skillOrAgent: string, routingType: string, reason?: string) => void;
  onQueued?: (requestId: string, position?: number) => void;
}

/**
 * File handling callbacks
 */
export interface IFileCallbacks {
  onFile?: (file: IncomingFile) => void;
  onFileSuggestion?: (file: FileSuggestion) => void;
}

/**
 * Interactive callbacks (questions, warnings)
 */
export interface IInteractiveCallbacks {
  onQuestion?: (question: string, options?: string[], requestId?: string) => void;
  onWarning?: (warning: string) => void;
}

/**
 * Error handling callbacks
 */
export interface IErrorCallbacks {
  onError?: (error: string, availableModels?: Array<{ name: string; supports_thinking?: boolean }>) => void;
  onCancelled?: (requestId?: string, reason?: string) => void;
}

/**
 * Conversation history callbacks
 */
export interface IHistoryCallbacks {
  onHistory?: (messages: HistoryMessage[]) => void;
  onCloseComplete?: (deletedCount: number) => void;
}

/**
 * Full callback interface - combines all segregated interfaces
 * Use this when you need all functionality
 */
export type IChatWebSocketCallbacks =
  ITextStreamCallbacks &
  IConnectionCallbacks &
  IRoutingCallbacks &
  IFileCallbacks &
  IInteractiveCallbacks &
  IErrorCallbacks &
  IHistoryCallbacks;

/**
 * Minimal callback interface - essential callbacks only
 * Use this for simple chat implementations
 */
export type IMinimalChatCallbacks =
  ITextStreamCallbacks &
  IConnectionCallbacks &
  IErrorCallbacks;

/**
 * File-aware callback interface
 * Use this when file handling is needed
 */
export type IFileAwareChatCallbacks =
  ITextStreamCallbacks &
  IConnectionCallbacks &
  IFileCallbacks &
  IErrorCallbacks;
