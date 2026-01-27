/**
 * File Message Handlers
 *
 * Handlers for file and file_suggestion messages.
 */

import type { IMessageHandler, HandlerContext, WebSocketMessage } from "./types";
import type { FileSource } from "@/core/types/file.types";

interface FileMessage extends WebSocketMessage {
  type: "file";
  filename?: string;
  base64_data?: string;
  filepath?: string;
  source?: FileSource;
  confidence?: number;
  mimetype?: string;
}

interface FileSuggestionMessage extends WebSocketMessage {
  type: "file_suggestion";
  filename?: string;
  base64_data?: string;
  filepath?: string;
  source?: FileSource;
  confidence?: number;
  mimetype?: string;
  needs_confirmation?: boolean;
}

/**
 * Handles file artifacts (high confidence)
 */
export class FileHandler implements IMessageHandler<FileMessage> {
  readonly messageType = "file";

  handle(message: FileMessage, context: HandlerContext): void {
    console.log(`[File] ${message.filename} (source: ${message.source}, confidence: ${message.confidence})`);
    context.callbacks.onFile?.({
      filename: message.filename || "untitled",
      base64Data: message.base64_data || "",
      source: message.source || "tool",
      confidence: message.confidence ?? 1.0,
      filepath: message.filepath,
      mimeType: message.mimetype,
    });
  }
}

/**
 * Handles file suggestions (needs confirmation)
 */
export class FileSuggestionHandler implements IMessageHandler<FileSuggestionMessage> {
  readonly messageType = "file_suggestion";

  handle(message: FileSuggestionMessage, context: HandlerContext): void {
    console.log(`[FileSuggestion] ${message.filename} (source: ${message.source}, confidence: ${message.confidence})`);
    context.callbacks.onFileSuggestion?.({
      filename: message.filename || "untitled",
      base64Data: message.base64_data || "",
      source: message.source || "llm_extraction",
      confidence: message.confidence ?? 0.8,
      filepath: message.filepath,
      mimeType: message.mimetype,
      suggested: true,
    });
  }
}
