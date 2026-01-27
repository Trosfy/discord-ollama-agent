/**
 * ChatWebSocket Client
 *
 * WebSocket client for real-time chat token streaming.
 * Handles connection, reconnection, and message streaming.
 */

import { API_CONFIG } from "@/config/api.config";
import type { IncomingFile, FileSuggestion, FileSource } from "@/core/types/file.types";

/**
 * File reference for chat attachments (TROISE-AI compatible)
 */
export interface ChatFileRef {
  file_id: string;
  filename?: string;
  mimetype: string;  // Changed from content_type to match TROISE-AI
  extracted_content?: string;
}

/**
 * User configuration overrides sent with messages
 */
export interface UserConfig {
  model?: string;
  temperature?: number;
  thinking_enabled?: boolean;
  enable_web_search?: boolean;
}

/**
 * TROISE-AI compatible message types
 */
export interface ChatMessage {
  type:
    // Streaming (TROISE-AI names)
    | "stream"        // Streaming token (was "token")
    | "stream_end"    // Stream finished
    | "response"      // Final response with metrics
    // Legacy (for backwards compatibility during transition)
    | "token"         // Alias for "stream"
    | "done"          // Alias for "stream_end" + "response"
    // Status
    | "session_start" // Connection established
    | "routing"       // Route decision made
    | "queued"        // Request queued
    // Interactive
    | "question"      // Agent asking user
    | "warning"       // Non-fatal issue (e.g., capability mismatch)
    // Files
    | "file"          // Generated file artifact
    | "file_suggestion" // Suggested file (needs confirmation)
    // Control
    | "error"         // Fatal error
    | "cancelled"     // Operation cancelled
    // History
    | "history"       // Conversation history
    | "close_complete"; // Conversation closed

  content?: string;
  tokensUsed?: number;
  outputTokens?: number;
  totalTokensGenerated?: number;
  generationTime?: number;
  model?: string;
  error?: string;
  warning?: string;
  session_id?: string;       // TROISE-AI uses session_id
  conversation_id?: string;  // Legacy alias
  deleted_count?: number;
  messages?: HistoryMessage[];
  // Routing info
  skill_or_agent?: string;
  routing_type?: string;
  reason?: string;
  // Queue info
  request_id?: string;
  position?: number;
  // Question info
  options?: string[];
  // File info (troise-ai protocol)
  filename?: string;
  base64_data?: string;
  filepath?: string;
  source?: FileSource;
  confidence?: number;
  mimetype?: string;
  needs_confirmation?: boolean;
  // Legacy field (deprecated)
  file_content?: string;
  language?: string;
  // Available models (for error responses)
  available_models?: Array<{
    name: string;
    supports_thinking?: boolean;
  }>;
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
  sessionId: string;
  userId: string;
  authToken?: string; // JWT token for authentication
  onToken: (token: string) => void;
  onDone: (tokensUsed?: number, generationTime?: number, outputTokens?: number, totalTokensGenerated?: number, model?: string) => void;
  onError: (error: string, availableModels?: Array<{ name: string; supports_thinking?: boolean }>) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onCloseComplete?: (deletedCount: number) => void;
  onHistory?: (messages: HistoryMessage[]) => void;
  // New TROISE-AI callbacks
  onSessionStart?: (sessionId: string) => void;
  onRouting?: (skillOrAgent: string, routingType: string, reason?: string) => void;
  onQueued?: (requestId: string, position?: number) => void;
  onWarning?: (warning: string) => void;
  onQuestion?: (question: string, options?: string[], requestId?: string) => void;
  onFile?: (file: IncomingFile) => void;
  onFileSuggestion?: (file: FileSuggestion) => void;
  onCancelled?: (requestId?: string, reason?: string) => void;
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
    const wsUrl = API_CONFIG.ENDPOINTS.WS.CHAT(
      this.config.sessionId,
      this.config.userId,
      this.config.authToken
    );
    console.log("[ChatWS] Attempting to connect to:", wsUrl.replace(/token=[^&]+/, "token=<redacted>"));
    console.log("[ChatWS] WS_BASE_URL:", API_CONFIG.WS_BASE_URL);

    try {
      this.isConnecting = true;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log(`[ChatWS] Connected: session=${this.config.sessionId}, user=${this.config.userId}`);
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        this.config.onConnect?.();
      };

      this.ws.onmessage = (event) => {
        try {
          const data: ChatMessage = JSON.parse(event.data);

          switch (data.type) {
            // Streaming tokens (TROISE-AI uses "stream", legacy uses "token")
            case "stream":
            case "token":
              if (data.content) {
                this.config.onToken(data.content);
              }
              break;

            // Stream end (TROISE-AI) - partial completion signal
            case "stream_end":
              console.log(`[ChatWS] Stream ended`);
              // Wait for "response" message with full metrics
              break;

            // Final response with metrics (TROISE-AI)
            case "response": {
              const visibleTokens = data.outputTokens;
              const totalTokens = data.totalTokensGenerated;
              const tokenDisplay = totalTokens && totalTokens !== visibleTokens
                ? `${visibleTokens} tokens (${totalTokens} total)`
                : `${visibleTokens || data.tokensUsed} tokens`;
              console.log(`[ChatWS] Response: ${tokenDisplay}, ${data.generationTime?.toFixed(2)}s, model: ${data.model}`);
              this.config.onDone(data.tokensUsed, data.generationTime, data.outputTokens, data.totalTokensGenerated, data.model);
              break;
            }

            // Legacy done message (combined stream_end + response)
            case "done": {
              const visibleTokens = data.outputTokens;
              const totalTokens = data.totalTokensGenerated;
              const tokenDisplay = totalTokens && totalTokens !== visibleTokens
                ? `${visibleTokens} tokens (${totalTokens} total)`
                : `${visibleTokens || data.tokensUsed} tokens`;
              console.log(`[ChatWS] Stream done: ${tokenDisplay}, ${data.generationTime?.toFixed(2)}s, model: ${data.model}`);
              this.config.onDone(data.tokensUsed, data.generationTime, data.outputTokens, data.totalTokensGenerated, data.model);
              break;
            }

            // Session established (TROISE-AI)
            case "session_start": {
              const sessionId = data.session_id || data.conversation_id;
              console.log(`[ChatWS] Session started: ${sessionId}`);
              this.config.onSessionStart?.(sessionId || this.config.sessionId);
              break;
            }

            // Routing decision made (TROISE-AI)
            case "routing":
              console.log(`[ChatWS] Routing: ${data.skill_or_agent} (${data.routing_type})`);
              this.config.onRouting?.(data.skill_or_agent || "", data.routing_type || "", data.reason);
              break;

            // Request queued (TROISE-AI)
            case "queued":
              console.log(`[ChatWS] Queued: ${data.request_id} at position ${data.position}`);
              this.config.onQueued?.(data.request_id || "", data.position);
              break;

            // Warning (non-fatal, e.g., capability mismatch)
            case "warning":
              console.warn(`[ChatWS] Warning:`, data.warning);
              this.config.onWarning?.(data.warning || "");
              break;

            // Agent asking user a question
            case "question":
              console.log(`[ChatWS] Question: ${data.content}`);
              this.config.onQuestion?.(data.content || "", data.options, data.request_id);
              break;

            // File artifact (high confidence)
            case "file":
              console.log(`[ChatWS] File: ${data.filename} (source: ${data.source}, confidence: ${data.confidence})`);
              this.config.onFile?.({
                filename: data.filename || "untitled",
                base64Data: data.base64_data || "",
                source: data.source || "tool",
                confidence: data.confidence ?? 1.0,
                filepath: data.filepath,
                mimeType: data.mimetype,
              });
              break;

            // File suggestion (needs confirmation)
            case "file_suggestion":
              console.log(`[ChatWS] File suggestion: ${data.filename} (source: ${data.source}, confidence: ${data.confidence})`);
              this.config.onFileSuggestion?.({
                filename: data.filename || "untitled",
                base64Data: data.base64_data || "",
                source: data.source || "llm_extraction",
                confidence: data.confidence ?? 0.8,
                filepath: data.filepath,
                mimeType: data.mimetype,
                suggested: true,
              });
              break;

            // Operation cancelled
            case "cancelled":
              console.log(`[ChatWS] Cancelled: ${data.reason}`);
              this.config.onCancelled?.(data.request_id, data.reason);
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
              this.config.onError(data.error || "Unknown error", data.available_models);
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
    userConfig?: UserConfig
  ): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error("[ChatWS] Cannot send: WebSocket not open");
      this.config.onError("Not connected");
      return;
    }

    // Transform file_refs to TROISE-AI compatible files format
    const files = fileRefs?.map((ref) => ({
      file_id: ref.file_id,
      filename: ref.filename,
      mimetype: ref.mimetype,
    }));

    const message: Record<string, unknown> = {
      type: "message",
      content,
      files,
    };

    // Only include user_config if any settings are provided
    if (userConfig && (userConfig.model || userConfig.temperature !== undefined ||
        userConfig.thinking_enabled !== undefined || userConfig.enable_web_search !== undefined)) {
      message.user_config = userConfig;
    }

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
      session_id: this.config.sessionId,
    };

    try {
      console.log(`[ChatWS] Sending close request for: ${this.config.sessionId}`);
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
      console.log(`[ChatWS] Requesting history for: ${this.config.sessionId}`);
      this.ws.send(JSON.stringify(message));
    } catch (err) {
      console.error("[ChatWS] Failed to request history:", err);
    }
  }

  /**
   * Cancel ongoing operation
   */
  cancel(requestId?: string, reason?: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error("[ChatWS] Cannot cancel: WebSocket not open");
      return;
    }

    const message = {
      type: "cancel",
      request_id: requestId,
      reason: reason || "User cancelled",
    };

    try {
      console.log(`[ChatWS] Sending cancel request`);
      this.ws.send(JSON.stringify(message));
    } catch (err) {
      console.error("[ChatWS] Failed to send cancel:", err);
    }
  }

  /**
   * Send answer to agent question
   */
  sendAnswer(requestId: string, answer: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error("[ChatWS] Cannot send answer: WebSocket not open");
      this.config.onError("Not connected");
      return;
    }

    const message = {
      type: "answer",
      request_id: requestId,
      answer,
    };

    try {
      console.log(`[ChatWS] Sending answer for request: ${requestId}`);
      this.ws.send(JSON.stringify(message));
    } catch (err) {
      console.error("[ChatWS] Failed to send answer:", err);
      this.config.onError("Failed to send answer");
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
