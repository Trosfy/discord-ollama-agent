/**
 * Control Message Handlers
 *
 * Handlers for session, routing, queue, and error messages.
 */

import type { IMessageHandler, HandlerContext, WebSocketMessage } from "./types";

interface SessionStartMessage extends WebSocketMessage {
  type: "session_start";
  conversation_id?: string;
}

interface RoutingMessage extends WebSocketMessage {
  type: "routing";
  skill_or_agent?: string;
  routing_type?: string;
  reason?: string;
}

interface QueuedMessage extends WebSocketMessage {
  type: "queued";
  request_id?: string;
  position?: number;
}

interface QuestionMessage extends WebSocketMessage {
  type: "question";
  content?: string;
  options?: string[];
  request_id?: string;
}

interface WarningMessage extends WebSocketMessage {
  type: "warning";
  warning?: string;
}

interface ErrorMessage extends WebSocketMessage {
  type: "error";
  error?: string;
  available_models?: Array<{ name: string; supports_thinking?: boolean }>;
}

interface CancelledMessage extends WebSocketMessage {
  type: "cancelled";
  request_id?: string;
  reason?: string;
}

interface HistoryMessage extends WebSocketMessage {
  type: "history";
  messages?: Array<{
    id: string;
    role: "user" | "assistant" | "system";
    content: string;
    timestamp: string;
    tokensUsed?: number;
    outputTokens?: number;
    totalTokensGenerated?: number;
    model?: string;
    generationTime?: number;
  }>;
}

interface CloseCompleteMessage extends WebSocketMessage {
  type: "close_complete";
  deleted_count?: number;
}

/**
 * Handles session_start message
 */
export class SessionStartHandler implements IMessageHandler<SessionStartMessage> {
  readonly messageType = "session_start";

  handle(message: SessionStartMessage, context: HandlerContext): void {
    console.log(`[SessionStart] Session: ${message.conversation_id}`);
    context.callbacks.onSessionStart?.(message.conversation_id || "");
  }
}

/**
 * Handles routing decision message
 */
export class RoutingHandler implements IMessageHandler<RoutingMessage> {
  readonly messageType = "routing";

  handle(message: RoutingMessage, context: HandlerContext): void {
    console.log(`[Routing] ${message.skill_or_agent} (${message.routing_type})`);
    context.callbacks.onRouting?.(
      message.skill_or_agent || "",
      message.routing_type || "",
      message.reason
    );
  }
}

/**
 * Handles queue status message
 */
export class QueuedHandler implements IMessageHandler<QueuedMessage> {
  readonly messageType = "queued";

  handle(message: QueuedMessage, context: HandlerContext): void {
    console.log(`[Queued] Request ${message.request_id} at position ${message.position}`);
    context.callbacks.onQueued?.(message.request_id || "", message.position);
  }
}

/**
 * Handles agent question message
 */
export class QuestionHandler implements IMessageHandler<QuestionMessage> {
  readonly messageType = "question";

  handle(message: QuestionMessage, context: HandlerContext): void {
    console.log(`[Question] ${message.content}`);
    context.callbacks.onQuestion?.(message.content || "", message.options, message.request_id);
  }
}

/**
 * Handles warning message (non-fatal)
 */
export class WarningHandler implements IMessageHandler<WarningMessage> {
  readonly messageType = "warning";

  handle(message: WarningMessage, context: HandlerContext): void {
    console.warn(`[Warning] ${message.warning}`);
    context.callbacks.onWarning?.(message.warning || "");
  }
}

/**
 * Handles error message
 */
export class ErrorHandler implements IMessageHandler<ErrorMessage> {
  readonly messageType = "error";

  handle(message: ErrorMessage, context: HandlerContext): void {
    console.error(`[Error] ${message.error}`);
    context.callbacks.onError?.(message.error || "Unknown error", message.available_models);
  }
}

/**
 * Handles cancelled message
 */
export class CancelledHandler implements IMessageHandler<CancelledMessage> {
  readonly messageType = "cancelled";

  handle(message: CancelledMessage, context: HandlerContext): void {
    console.log(`[Cancelled] ${message.reason}`);
    context.callbacks.onCancelled?.(message.request_id, message.reason);
  }
}

/**
 * Handles history message
 */
export class HistoryHandler implements IMessageHandler<HistoryMessage> {
  readonly messageType = "history";

  handle(message: HistoryMessage, context: HandlerContext): void {
    console.log(`[History] ${message.messages?.length || 0} messages`);
    context.callbacks.onHistory?.(message.messages || []);
  }
}

/**
 * Handles close_complete message
 */
export class CloseCompleteHandler implements IMessageHandler<CloseCompleteMessage> {
  readonly messageType = "close_complete";

  handle(message: CloseCompleteMessage, context: HandlerContext): void {
    console.log(`[CloseComplete] ${message.deleted_count} messages deleted`);
    context.callbacks.onCloseComplete?.(message.deleted_count || 0);
  }
}
