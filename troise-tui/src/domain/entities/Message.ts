/**
 * Message entity - represents a chat message in the conversation.
 */
export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  metadata?: MessageMetadata;
}

export interface MessageMetadata {
  /** Model that generated this response */
  model?: string;
  /** Tokens used in response */
  tokens?: number;
  /** Response generation time in ms */
  responseTime?: number;
  /** Tool calls made during response */
  toolCalls?: ToolCall[];
  /** Files attached to message */
  attachments?: FileAttachment[];
  /** Whether message is streaming */
  isStreaming?: boolean;
  /** Request ID for tracking */
  requestId?: string;
  /** Source skill/agent that generated response */
  source?: {
    type: "skill" | "agent";
    name: string;
  };
}

export interface ToolCall {
  id: string;
  name: string;
  arguments?: Record<string, unknown>;
  result?: string;
}

export interface FileAttachment {
  id: string;
  filename: string;
  mimetype: string;
  size: number;
  /** Base64 encoded content (for sending) */
  base64Data?: string;
  /** Extracted text content (from server) */
  extractedContent?: string;
}

/**
 * Create a new user message
 */
export function createUserMessage(
  content: string,
  attachments?: FileAttachment[]
): Message {
  return {
    id: crypto.randomUUID(),
    role: "user",
    content,
    timestamp: new Date(),
    metadata: attachments ? { attachments } : undefined,
  };
}

/**
 * Create a new assistant message
 */
export function createAssistantMessage(
  content: string,
  metadata?: Partial<MessageMetadata>
): Message {
  return {
    id: crypto.randomUUID(),
    role: "assistant",
    content,
    timestamp: new Date(),
    metadata,
  };
}

/**
 * Create a streaming message placeholder
 */
export function createStreamingMessage(requestId: string): Message {
  return {
    id: crypto.randomUUID(),
    role: "assistant",
    content: "",
    timestamp: new Date(),
    metadata: {
      isStreaming: true,
      requestId,
    },
  };
}
