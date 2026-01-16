import type { Message, Session, SessionSummary } from "@domain/entities";

/**
 * Session store interface for persisting chat sessions locally.
 */
export interface ISessionStore {
  /**
   * Get session by ID
   */
  getSession(sessionId: string): Promise<Session | undefined>;

  /**
   * List all sessions
   */
  listSessions(options?: ListSessionsOptions): Promise<SessionSummary[]>;

  /**
   * Save session
   */
  saveSession(session: Session): Promise<void>;

  /**
   * Delete session
   */
  deleteSession(sessionId: string): Promise<void>;

  /**
   * Get messages for a session
   */
  getMessages(sessionId: string, options?: GetMessagesOptions): Promise<Message[]>;

  /**
   * Save message to session
   */
  saveMessage(sessionId: string, message: Message): Promise<void>;

  /**
   * Search sessions
   */
  searchSessions(query: string): Promise<SessionSummary[]>;

  /**
   * Export session to file
   */
  exportSession(sessionId: string, format: ExportFormat): Promise<string>;

  /**
   * Import session from file
   */
  importSession(content: string, format: ExportFormat): Promise<Session>;

  /**
   * Add tag to session
   */
  addTag(sessionId: string, tag: string): Promise<void>;

  /**
   * Remove tag from session
   */
  removeTag(sessionId: string, tag: string): Promise<void>;

  /**
   * Toggle bookmark on session
   */
  toggleBookmark(sessionId: string): Promise<void>;
}

export interface ListSessionsOptions {
  limit?: number;
  offset?: number;
  sortBy?: "updatedAt" | "createdAt" | "messageCount";
  sortOrder?: "asc" | "desc";
  tags?: string[];
  bookmarkedOnly?: boolean;
}

export interface GetMessagesOptions {
  limit?: number;
  beforeTimestamp?: Date;
  afterTimestamp?: Date;
}

export type ExportFormat = "json" | "markdown" | "html";
