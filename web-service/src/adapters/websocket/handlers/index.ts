/**
 * WebSocket Message Handlers - Public Exports
 *
 * Exports the handler registry and all handlers.
 */

// Types
export type {
  WebSocketMessage,
  HandlerContext,
  MessageCallbacks,
  IMessageHandler,
} from "./types";

// Registry
export { MessageHandlerRegistry } from "./registry";

// Stream handlers
export {
  StreamHandler,
  TokenHandler,
  StreamEndHandler,
  ResponseHandler,
  DoneHandler,
} from "./StreamHandlers";

// File handlers
export {
  FileHandler,
  FileSuggestionHandler,
} from "./FileHandlers";

// Control handlers
export {
  SessionStartHandler,
  RoutingHandler,
  QueuedHandler,
  QuestionHandler,
  WarningHandler,
  ErrorHandler,
  CancelledHandler,
  HistoryHandler,
  CloseCompleteHandler,
} from "./ControlHandlers";

// Factory
import { MessageHandlerRegistry } from "./registry";
import { StreamHandler, TokenHandler, StreamEndHandler, ResponseHandler, DoneHandler } from "./StreamHandlers";
import { FileHandler, FileSuggestionHandler } from "./FileHandlers";
import {
  SessionStartHandler,
  RoutingHandler,
  QueuedHandler,
  QuestionHandler,
  WarningHandler,
  ErrorHandler,
  CancelledHandler,
  HistoryHandler,
  CloseCompleteHandler,
} from "./ControlHandlers";

/**
 * Create a registry with all default handlers registered
 */
export function createDefaultRegistry(): MessageHandlerRegistry {
  const registry = new MessageHandlerRegistry();

  // Stream handlers
  registry.register(new StreamHandler());
  registry.register(new TokenHandler());
  registry.register(new StreamEndHandler());
  registry.register(new ResponseHandler());
  registry.register(new DoneHandler());

  // File handlers
  registry.register(new FileHandler());
  registry.register(new FileSuggestionHandler());

  // Control handlers
  registry.register(new SessionStartHandler());
  registry.register(new RoutingHandler());
  registry.register(new QueuedHandler());
  registry.register(new QuestionHandler());
  registry.register(new WarningHandler());
  registry.register(new ErrorHandler());
  registry.register(new CancelledHandler());
  registry.register(new HistoryHandler());
  registry.register(new CloseCompleteHandler());

  return registry;
}
