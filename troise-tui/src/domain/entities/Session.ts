/**
 * Session entity - represents a chat session with history.
 */
export interface Session {
  id: string;
  userId: string;
  title?: string;
  interface: "cli";
  createdAt: Date;
  updatedAt: Date;
  messageCount: number;
  /** Last used agent/skill */
  agentName?: string;
  /** Tags for organization */
  tags?: string[];
  /** Whether session is bookmarked */
  bookmarked?: boolean;
}

/**
 * Session summary for history list
 */
export interface SessionSummary {
  id: string;
  title: string;
  preview: string;
  messageCount: number;
  updatedAt: Date;
  tags?: string[];
  bookmarked?: boolean;
}

/**
 * Create a new session
 */
export function createSession(userId: string): Session {
  return {
    id: crypto.randomUUID(),
    userId,
    interface: "cli",
    createdAt: new Date(),
    updatedAt: new Date(),
    messageCount: 0,
  };
}

/**
 * Update session after a message exchange
 */
export function updateSession(
  session: Session,
  updates: Partial<Pick<Session, "title" | "agentName" | "tags" | "bookmarked">>
): Session {
  return {
    ...session,
    ...updates,
    updatedAt: new Date(),
    messageCount: session.messageCount + 1,
  };
}

/**
 * Generate session title from first message
 */
export function generateSessionTitle(firstMessage: string): string {
  const maxLength = 50;
  const cleaned = firstMessage.replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLength) {
    return cleaned;
  }
  return `${cleaned.substring(0, maxLength - 3)}...`;
}
