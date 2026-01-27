/**
 * Streaming Message Handlers
 *
 * Handlers for token streaming and response messages.
 */

import type { IMessageHandler, HandlerContext, WebSocketMessage } from "./types";

interface StreamMessage extends WebSocketMessage {
  type: "stream" | "token";
  content?: string;
}

interface StreamEndMessage extends WebSocketMessage {
  type: "stream_end";
}

interface ResponseMessage extends WebSocketMessage {
  type: "response" | "done";
  tokensUsed?: number;
  outputTokens?: number;
  totalTokensGenerated?: number;
  reasoningTokens?: number;
  generationTime?: number;
  model?: string;
}

/**
 * Handles streaming tokens (stream/token messages)
 */
export class StreamHandler implements IMessageHandler<StreamMessage> {
  readonly messageType = "stream";

  handle(message: StreamMessage, context: HandlerContext): void {
    if (message.content) {
      context.callbacks.onToken?.(message.content);
    }
  }
}

/**
 * Legacy token handler (alias for stream)
 */
export class TokenHandler implements IMessageHandler<StreamMessage> {
  readonly messageType = "token";

  handle(message: StreamMessage, context: HandlerContext): void {
    if (message.content) {
      context.callbacks.onToken?.(message.content);
    }
  }
}

/**
 * Handles stream end (intermediate signal)
 */
export class StreamEndHandler implements IMessageHandler<StreamEndMessage> {
  readonly messageType = "stream_end";

  handle(_message: StreamEndMessage, _context: HandlerContext): void {
    // Stream end is an intermediate signal - wait for response message
    console.log("[StreamEnd] Stream ended, waiting for response");
  }
}

/**
 * Handles response with metrics (TROISE-AI)
 */
export class ResponseHandler implements IMessageHandler<ResponseMessage> {
  readonly messageType = "response";

  handle(message: ResponseMessage, context: HandlerContext): void {
    const visibleTokens = message.outputTokens;
    const totalTokens = message.totalTokensGenerated;
    const tokenDisplay = totalTokens && totalTokens !== visibleTokens
      ? `${visibleTokens} tokens (${totalTokens} total)`
      : `${visibleTokens || message.tokensUsed} tokens`;
    console.log(`[Response] ${tokenDisplay}, ${message.generationTime?.toFixed(2)}s, model: ${message.model}`);
    context.callbacks.onDone?.(
      message.tokensUsed,
      message.generationTime,
      message.outputTokens,
      message.totalTokensGenerated,
      message.model
    );
  }
}

/**
 * Legacy done handler (combined stream_end + response)
 */
export class DoneHandler implements IMessageHandler<ResponseMessage> {
  readonly messageType = "done";

  handle(message: ResponseMessage, context: HandlerContext): void {
    const visibleTokens = message.outputTokens;
    const totalTokens = message.totalTokensGenerated;
    const tokenDisplay = totalTokens && totalTokens !== visibleTokens
      ? `${visibleTokens} tokens (${totalTokens} total)`
      : `${visibleTokens || message.tokensUsed} tokens`;
    console.log(`[Done] ${tokenDisplay}, ${message.generationTime?.toFixed(2)}s, model: ${message.model}`);
    context.callbacks.onDone?.(
      message.tokensUsed,
      message.generationTime,
      message.outputTokens,
      message.totalTokensGenerated,
      message.model
    );
  }
}
