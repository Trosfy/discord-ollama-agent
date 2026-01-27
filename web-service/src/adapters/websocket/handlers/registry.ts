/**
 * Message Handler Registry
 *
 * Manages message handlers for WebSocket messages.
 * Follows OCP - register new handlers without modifying existing code.
 */

import type { IMessageHandler, WebSocketMessage, HandlerContext } from "./types";

export class MessageHandlerRegistry {
  private handlers = new Map<string, IMessageHandler>();

  /**
   * Register a handler for a message type
   * @param handler - The handler to register
   */
  register(handler: IMessageHandler): void {
    if (this.handlers.has(handler.messageType)) {
      console.warn(`[Registry] Handler for "${handler.messageType}" already registered, overwriting`);
    }
    this.handlers.set(handler.messageType, handler);
  }

  /**
   * Unregister a handler
   * @param messageType - The message type to unregister
   */
  unregister(messageType: string): void {
    this.handlers.delete(messageType);
  }

  /**
   * Process a message with the appropriate handler
   * @param message - The WebSocket message
   * @param context - Handler context
   * @returns true if a handler was found and executed
   */
  handle(message: WebSocketMessage, context: HandlerContext): boolean {
    const handler = this.handlers.get(message.type);
    if (handler) {
      try {
        handler.handle(message, context);
        return true;
      } catch (error) {
        console.error(`[Registry] Handler for "${message.type}" threw error:`, error);
        return false;
      }
    }
    return false;
  }

  /**
   * Check if a handler exists for a message type
   */
  hasHandler(messageType: string): boolean {
    return this.handlers.has(messageType);
  }

  /**
   * Get all registered message types
   */
  getRegisteredTypes(): string[] {
    return Array.from(this.handlers.keys());
  }
}
