/**
 * Conversation API Service
 *
 * Service for managing conversations via WebSocket.
 * Handles close/delete operations by opening a temporary connection.
 */

import { API_CONFIG } from "@/config/api.config";

export interface CloseConversationResult {
  success: boolean;
  deletedCount?: number;
  error?: string;
}

/**
 * Close a conversation and delete all messages from DynamoDB
 * Opens a temporary WebSocket connection, sends close command, and waits for response
 */
export async function closeConversation(conversationId: string): Promise<CloseConversationResult> {
  return new Promise((resolve) => {
    const wsUrl = API_CONFIG.ENDPOINTS.WS.CHAT(conversationId);
    console.log(`[ConversationAPI] Closing conversation: ${conversationId}`);

    let ws: WebSocket | null = null;
    let timeoutId: NodeJS.Timeout | null = null;

    const cleanup = () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      if (ws) {
        ws.close();
        ws = null;
      }
    };

    try {
      ws = new WebSocket(wsUrl);

      // Timeout after 10 seconds
      timeoutId = setTimeout(() => {
        console.error("[ConversationAPI] Close request timed out");
        cleanup();
        resolve({ success: false, error: "Request timed out" });
      }, 10000);

      ws.onopen = () => {
        console.log(`[ConversationAPI] Connected, sending close request`);
        ws?.send(JSON.stringify({
          type: "close",
          conversation_id: conversationId,
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === "close_complete") {
            console.log(`[ConversationAPI] Close complete: ${data.deleted_count} messages deleted`);
            cleanup();
            resolve({ success: true, deletedCount: data.deleted_count });
          } else if (data.type === "error") {
            console.error(`[ConversationAPI] Error:`, data.error);
            cleanup();
            resolve({ success: false, error: data.error });
          }
        } catch (err) {
          console.error("[ConversationAPI] Failed to parse message:", err);
        }
      };

      ws.onerror = (error) => {
        console.error("[ConversationAPI] WebSocket error:", error);
        cleanup();
        resolve({ success: false, error: "Connection error" });
      };

      ws.onclose = () => {
        // If we haven't resolved yet, treat as success (connection closed normally)
        console.log("[ConversationAPI] Connection closed");
      };
    } catch (err) {
      console.error("[ConversationAPI] Failed to create WebSocket:", err);
      cleanup();
      resolve({ success: false, error: "Failed to connect" });
    }
  });
}

/**
 * Archive a conversation (mark as archived in local store)
 * Note: Backend archive functionality can be added later
 */
export async function archiveConversation(conversationId: string): Promise<boolean> {
  // For now, this is a local-only operation
  // Can be extended to call backend API
  console.log(`[ConversationAPI] Archiving conversation: ${conversationId}`);
  return true;
}

/**
 * Pin a conversation
 * Note: Backend pin functionality can be added later
 */
export async function pinConversation(conversationId: string): Promise<boolean> {
  console.log(`[ConversationAPI] Pinning conversation: ${conversationId}`);
  return true;
}

/**
 * Clone a conversation
 * Note: Backend clone functionality can be added later
 */
export async function cloneConversation(conversationId: string): Promise<string | null> {
  console.log(`[ConversationAPI] Cloning conversation: ${conversationId}`);
  // Return new conversation ID
  return null;
}

/**
 * Export/Download conversation as JSON
 */
export function downloadConversation(conversationId: string, messages: unknown[]): void {
  console.log(`[ConversationAPI] Downloading conversation: ${conversationId}`);
  
  const data = {
    conversationId,
    exportedAt: new Date().toISOString(),
    messages,
  };

  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `conversation-${conversationId}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Share conversation (copy link or generate share URL)
 */
export function shareConversation(conversationId: string): void {
  console.log(`[ConversationAPI] Sharing conversation: ${conversationId}`);
  
  const shareUrl = `${window.location.origin}/chat/${conversationId}`;
  navigator.clipboard.writeText(shareUrl).then(() => {
    console.log("[ConversationAPI] Share URL copied to clipboard");
  }).catch((err) => {
    console.error("[ConversationAPI] Failed to copy share URL:", err);
  });
}
