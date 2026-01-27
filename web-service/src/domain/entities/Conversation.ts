/**
 * Domain Entity - Conversation
 *
 * Represents a conversation between a user and Trollama.
 * Note: We use "conversation" terminology, not "thread" (per user requirement)
 * Part of the Domain Layer (SOLID Architecture)
 */

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date | string;  // Date in memory, string when serialized
  tokensUsed?: number;
  outputTokens?: number;  // Output tokens (excluding thinking)
  totalTokensGenerated?: number;  // Total tokens including thinking (for TPS)
  generationTime?: number;  // Seconds taken to generate
  model?: string;  // Model used to generate this message
  attachments?: MessageAttachment[];
}

export interface MessageAttachment {
  id: string;
  type: "image" | "document" | "code";
  filename: string;
  size: number;
  mimeType: string;
  url?: string;
  base64?: string;
}

export interface Conversation {
  id: string;
  userId: string;
  title?: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  model?: string;
  archived: boolean;
  pinned?: boolean;  // Pin conversation to top of list
}

export type ConversationSummary = Pick<Conversation, "id" | "title" | "createdAt" | "updatedAt"> & {
  messageCount: number;
  lastMessage?: string;
};
