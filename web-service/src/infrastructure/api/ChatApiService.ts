/**
 * Chat API Service
 *
 * Implementation of IChatService using HTTP API (polling).
 * Part of the Infrastructure Layer (SOLID Architecture)
 *
 * Note: For real-time streaming, use ChatWebSocket instead.
 */

import {
  IChatService,
  SendMessageRequest,
  SendMessageResponse,
  MessageStatusResponse,
} from "@/domain/interfaces/IChatService";
import { Conversation, ConversationSummary } from "@/domain/entities/Conversation";
import { ApiResponse } from "@/domain/types/ApiResponse";
import { httpClient, handleApiError } from "./HttpClient";
import { API_CONFIG } from "@/config/api.config";

export class ChatApiService implements IChatService {
  async sendMessage(
    request: SendMessageRequest
  ): Promise<ApiResponse<SendMessageResponse>> {
    try {
      const response = await httpClient.post<{ data: SendMessageResponse }>(
        API_CONFIG.ENDPOINTS.CHAT.SEND,
        request
      );

      return {
        success: true,
        data: response.data.data,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  async getMessageStatus(
    requestId: string
  ): Promise<ApiResponse<MessageStatusResponse>> {
    try {
      const response = await httpClient.get<{ data: MessageStatusResponse }>(
        API_CONFIG.ENDPOINTS.CHAT.STATUS(requestId)
      );

      return {
        success: true,
        data: response.data.data,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  async getConversation(conversationId: string): Promise<ApiResponse<Conversation>> {
    try {
      const response = await httpClient.get<{ data: Conversation }>(
        API_CONFIG.ENDPOINTS.CHAT.CONVERSATION(conversationId)
      );

      return {
        success: true,
        data: response.data.data,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  async listConversations(
    userId: string
  ): Promise<ApiResponse<ConversationSummary[]>> {
    try {
      const response = await httpClient.get<{ data: ConversationSummary[] }>(
        API_CONFIG.ENDPOINTS.CHAT.LIST(userId)
      );

      return {
        success: true,
        data: response.data.data,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  async createConversation(
    userId: string,
    title?: string
  ): Promise<ApiResponse<Conversation>> {
    try {
      const response = await httpClient.post<{ data: Conversation }>(
        API_CONFIG.ENDPOINTS.CHAT.CREATE,
        { userId, title }
      );

      return {
        success: true,
        data: response.data.data,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  async deleteConversation(conversationId: string): Promise<ApiResponse<void>> {
    try {
      await httpClient.delete(API_CONFIG.ENDPOINTS.CHAT.DELETE(conversationId));

      return {
        success: true,
        data: undefined,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }

  async regenerateMessage(
    conversationId: string,
    messageId: string
  ): Promise<ApiResponse<SendMessageResponse>> {
    try {
      const response = await httpClient.post<{ data: SendMessageResponse }>(
        API_CONFIG.ENDPOINTS.CHAT.REGENERATE(conversationId, messageId)
      );

      return {
        success: true,
        data: response.data.data,
      };
    } catch (error) {
      return {
        success: false,
        error: handleApiError(error),
      };
    }
  }
}

// Export singleton instance
export const chatApiService = new ChatApiService();
