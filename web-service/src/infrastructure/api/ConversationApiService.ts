/**
 * Conversation API Service
 *
 * Service for managing conversations via REST API.
 * Handles CRUD operations for conversations.
 */

import { API_CONFIG } from "@/config/api.config";

export interface CloseConversationResult {
  success: boolean;
  deletedCount?: number;
  error?: string;
}

/**
 * Delete a conversation and all messages from DynamoDB via REST API
 */
export async function closeConversation(
  conversationId: string,
  userId: string
): Promise<CloseConversationResult> {
  const deleteUrl = `${API_CONFIG.BASE_URL}/sessions/${userId}/${conversationId}`;
  console.log(`[ConversationAPI] Deleting conversation: ${conversationId}`);

  try {
    const response = await fetch(deleteUrl, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    });

    if (response.ok) {
      const data = await response.json();
      console.log(`[ConversationAPI] Delete complete: ${data.session_id}`);
      return { success: true, deletedCount: 1 };
    } else if (response.status === 404) {
      // Session not found in backend = treat as success (local-only conversation)
      console.log(`[ConversationAPI] Session not in backend, removing locally`);
      return { success: true, deletedCount: 0 };
    } else {
      const errorData = await response.json().catch(() => ({}));
      console.error(`[ConversationAPI] Delete failed:`, errorData);
      return { success: false, error: errorData.detail || "Delete failed" };
    }
  } catch (err) {
    console.error("[ConversationAPI] Delete request failed:", err);
    return { success: false, error: "Network error" };
  }
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
