/**
 * Domain Interface - IChatService
 *
 * Defines the contract for chat services.
 * Part of the Domain Layer (SOLID Architecture)
 *
 * Implementations:
 * - infrastructure/api/ChatApiService.ts (HTTP polling)
 * - infrastructure/websocket/ChatWebSocket.ts (WebSocket streaming)
 */

import { Conversation, ConversationSummary, Message } from "../entities/Conversation";
import { ApiResponse } from "../types/ApiResponse";

export interface SendMessageRequest {
  conversationId: string;
  message: string;
  attachments?: Array<{
    filename: string;
    mimeType: string;
    base64: string;
  }>;
  model?: string;
  temperature?: number;
  enableWebSearch?: boolean;
}

export interface SendMessageResponse {
  requestId: string;
  queuePosition?: number;
  status: "queued" | "processing" | "completed" | "failed";
}

export interface MessageStatusResponse {
  status: "queued" | "processing" | "completed" | "failed";
  queuePosition?: number;
  response?: string;
  tokensUsed?: number;
  error?: string;
}

export interface IChatService {
  /**
   * Send a message to a conversation
   */
  sendMessage(request: SendMessageRequest): Promise<ApiResponse<SendMessageResponse>>;

  /**
   * Poll for message status
   */
  getMessageStatus(requestId: string): Promise<ApiResponse<MessageStatusResponse>>;

  /**
   * Get conversation history
   */
  getConversation(conversationId: string): Promise<ApiResponse<Conversation>>;

  /**
   * List user's conversations
   */
  listConversations(userId: string): Promise<ApiResponse<ConversationSummary[]>>;

  /**
   * Create a new conversation
   */
  createConversation(userId: string, title?: string): Promise<ApiResponse<Conversation>>;

  /**
   * Delete a conversation
   */
  deleteConversation(conversationId: string): Promise<ApiResponse<void>>;

  /**
   * Regenerate last assistant message
   */
  regenerateMessage(conversationId: string, messageId: string): Promise<ApiResponse<SendMessageResponse>>;
}
