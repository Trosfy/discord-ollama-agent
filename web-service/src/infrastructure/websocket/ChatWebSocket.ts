/**
 * ChatWebSocket Client
 *
 * WebSocket client for real-time chat token streaming.
 * Handles connection, reconnection, and message streaming.
 */

import { API_CONFIG } from "@/config/api.config";

/**
 * File reference for chat attachments
 */
export interface ChatFileRef {
  file_id: string;
  filename: string;
  content_type: string;
  extracted_content?: string;
}

export interface ChatMessage {
  type: "token" | "done" | "error" | "close_complete" | "history";
  content?: string;
  tokensUsed?: number;
  outputTokens?: number;  // Visible output tokens (for display)
  totalTokensGenerated?: number;  // Total tokens including thinking (for TPS)
  generationTime?: number;  // seconds
  model?: string;  // Model used for this response
  error?: string;
  conversation_id?: string;
  deleted_count?: number;
  messages?: HistoryMessage[];
}

export interface HistoryMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  tokensUsed?: number;
  outputTokens?: number;  // Visible output tokens (for display)
  totalTokensGenerated?: number;  // Total tokens including thinking (for TPS)
  model?: string; // Model used to generate this message
  generationTime?: number; // Seconds taken to generate (for tokens/sec calculation)
}

export interface ChatWebSocketConfig {
  conversationId: string;
  onToken: (token: string) => void;
  onDone: (tokensUsed?: number, generationTime?: number, outputTokens?: number, totalTokensGenerated?: number, model?: string) => void;
  onError: (error: string) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onCloseComplete?: (deletedCount: number) => void;
  onHistory?: (messages: HistoryMessage[]) => void;
}

export class ChatWebSocketClient {
  private ws: WebSocket | null = null;
  private config: ChatWebSocketConfig;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private isManualClose = false;
  private isConnecting = false;

  constructor(config: ChatWebSocketConfig) {
    this.config = config;
  }

  /**
   * Connect to WebSocket
   */
  connect(): void {
    const wsUrl = API_CONFIG.ENDPOINTS.WS.CHAT(this.config.conversationId);
    console.log("[ChatWS] Attempting to connect to:", wsUrl);
    console.log("[ChatWS] WS_BASE_URL:", API_CONFIG.WS_BASE_URL);

    try {
      this.isConnecting = true;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log(`[ChatWS] Connected: ${this.config.conversationId}`);
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        this.config.onConnect?.();
      };

      this.ws.onmessage = (event) => {
        try {
          const data: ChatMessage = JSON.parse(event.data);

          switch (data.type) {
            case "token":
              if (data.content) {
                this.config.onToken(data.content);
              }
              break;

            case "done":
              console.log(`[ChatWS] Stream done: ${data.outputTokens || data.tokensUsed} tokens, ${data.generationTime?.toFixed(2)}s, model: ${data.model}`);
              this.config.onDone(data.tokensUsed, data.generationTime, data.outputTokens, data.totalTokensGenerated, data.model);
              break;

            case "close_complete":
              console.log(`[ChatWS] Close complete: ${data.deleted_count} messages deleted`);
              this.config.onCloseComplete?.(data.deleted_count || 0);
              break;

            case "history":
              console.log(`[ChatWS] History received: ${data.messages?.length || 0} messages`);
              this.config.onHistory?.(data.messages || []);
              break;

            case "error":
              console.error(`[ChatWS] Error:`, data.error);
              this.config.onError(data.error || "Unknown error");
              break;
          }
        } catch (err) {
          console.error("[ChatWS] Failed to parse message:", err);
        }
      };

      this.ws.onerror = (error) => {
        console.error("[ChatWS] WebSocket error:", error);
        // Only show error to user if we've exhausted reconnection attempts
        // During initial connection or reconnection, suppress the error
        if (!this.isConnecting && this.reconnectAttempts >= this.maxReconnectAttempts) {
          this.config.onError("Connection error");
        }
      };

      this.ws.onclose = () => {
        console.log("[ChatWS] Disconnected");
        this.isConnecting = false;
        this.config.onDisconnect?.();

        // Attempt reconnection if not manually closed
        if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          console.log(`[ChatWS] Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

          setTimeout(() => {
            this.connect();
          }, this.reconnectDelay * this.reconnectAttempts);
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
          // Only show error after all reconnection attempts failed
          this.config.onError("Failed to connect after multiple attempts");
        }
      };
    } catch (err) {
      console.error("[ChatWS] Failed to create WebSocket:", err);
      this.isConnecting = false;

      // Try reconnection if available and not manually closed
      if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.log(`[ChatWS] Reconnecting after error... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        setTimeout(() => {
          this.connect();
        }, this.reconnectDelay * this.reconnectAttempts);
      } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        this.config.onError("Failed to connect after multiple attempts");
      }
    }
  }

  /**
   * Send message to chat
   */
  sendMessage(
    content: string,
    fileRefs?: ChatFileRef[],
    model?: string,
    temperature?: number,
    thinkingEnabled?: boolean
  ): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error("[ChatWS] Cannot send: WebSocket not open");
      this.config.onError("Not connected");
      return;
    }

    const message = {
      type: "message",
      content,
      model: model, // Send undefined → backend router decides
      temperature: temperature ?? 0.7,
      thinking_enabled: thinkingEnabled ?? true,
      enable_web_search: true,
      file_refs: fileRefs,
    };

    try {
      this.ws.send(JSON.stringify(message));
    } catch (err) {
      console.error("[ChatWS] Failed to send message:", err);
      this.config.onError("Failed to send message");
    }
  }

  /**
   * Close conversation and delete from backend
   */
  closeConversation(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error("[ChatWS] Cannot close: WebSocket not open");
      this.config.onError("Not connected");
      return;
    }

    const message = {
      type: "close",
      conversation_id: this.config.conversationId,
    };

    try {
      console.log(`[ChatWS] Sending close request for: ${this.config.conversationId}`);
      this.ws.send(JSON.stringify(message));
    } catch (err) {
      console.error("[ChatWS] Failed to close conversation:", err);
      this.config.onError("Failed to close conversation");
    }
  }

  /**
   * Request conversation history from backend
   */
  requestHistory(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error("[ChatWS] Cannot request history: WebSocket not open");
      return;
    }

    const message = {
      type: "history",
    };

    try {
      console.log(`[ChatWS] Requesting history for: ${this.config.conversationId}`);
      this.ws.send(JSON.stringify(message));
    } catch (err) {
      console.error("[ChatWS] Failed to request history:", err);
    }
  }

  /**
   * Disconnect WebSocket
   */
  disconnect(): void {
    this.isManualClose = true;
    this.isConnecting = false;

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Get connection state
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}
