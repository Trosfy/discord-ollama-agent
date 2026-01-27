/**
 * File Upload Service
 *
 * Infrastructure service for uploading files to the backend.
 * Follows SOLID principles - Single Responsibility for file uploads.
 *
 * Adapted for TROISE-AI compatibility:
 * - Endpoint: /files/upload
 * - Form field: session_id (instead of user_id)
 * - Response: files[] with mimetype (instead of file_refs[] with content_type)
 */

import { httpClient } from "./HttpClient";
import { API_CONFIG } from "@/config/api.config";
import { FileAttachment } from "@/domain/types/attachment.types";
import { ChatFileRef } from "@/infrastructure/websocket/ChatWebSocket";

/**
 * Response from TROISE-AI backend for a single uploaded file
 */
export interface FileUploadResponse {
  file_id: string;
  filename: string;
  mimetype: string;  // TROISE-AI uses mimetype instead of content_type
  size: number;
  extracted_content?: string;
}

/**
 * Response from TROISE-AI backend for multi-file upload
 */
export interface TroiseFileUploadResponse {
  session_id: string;
  files: FileUploadResponse[];
  count: number;
}

/**
 * Error response structure
 */
export interface UploadErrorResponse {
  files: FileUploadResponse[];
  errors: Array<{
    filename: string;
    error: string;
  }>;
}

/**
 * Options for upload progress tracking
 */
export interface UploadOptions {
  onProgress?: (progress: number) => void;
  sessionId?: string;  // Session ID for TROISE-AI
}

/**
 * File Upload Service
 */
export class FileUploadService {
  private static readonly MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

  /**
   * Upload a single file to the backend
   */
  static async uploadFile(
    attachment: FileAttachment,
    options?: UploadOptions
  ): Promise<FileUploadResponse> {
    const result = await this.uploadFiles([attachment], options);

    if (result.files.length > 0) {
      return result.files[0];
    }

    if (result.errors.length > 0) {
      throw new Error(result.errors[0].error);
    }

    throw new Error("Unknown upload error");
  }

  /**
   * Upload multiple files to the backend
   */
  static async uploadFiles(
    attachments: FileAttachment[],
    options?: UploadOptions
  ): Promise<UploadErrorResponse> {
    // Validate files before upload
    for (const attachment of attachments) {
      if (attachment.size > this.MAX_FILE_SIZE) {
        throw new Error(
          `File "${attachment.name}" exceeds maximum size of ${this.MAX_FILE_SIZE / 1024 / 1024}MB`
        );
      }
    }

    // Build FormData
    const formData = new FormData();
    for (const attachment of attachments) {
      formData.append("files", attachment.file);
    }

    // Add session ID (TROISE-AI expects session_id, not user_id)
    formData.append("session_id", options?.sessionId || "webui_session");

    try {
      const response = await httpClient.post<TroiseFileUploadResponse>(
        API_CONFIG.ENDPOINTS.FILES.UPLOAD,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
          timeout: 120000, // 120s timeout for OCR processing
          onUploadProgress: (progressEvent) => {
            if (options?.onProgress && progressEvent.total) {
              const progress = Math.round(
                (progressEvent.loaded * 100) / progressEvent.total
              );
              options.onProgress(progress);
            }
          },
        }
      );

      // Transform TROISE-AI response to our format
      return {
        files: response.data.files,
        errors: [],
      };
    } catch (error) {
      console.error("File upload failed:", error);

      // Return error response
      return {
        files: [],
        errors: attachments.map((a) => ({
          filename: a.name,
          error: error instanceof Error ? error.message : "Upload failed",
        })),
      };
    }
  }

  /**
   * Delete an uploaded file from the backend
   */
  static async deleteFile(fileId: string): Promise<boolean> {
    try {
      await httpClient.delete(`/files/${fileId}`);
      return true;
    } catch (error) {
      console.error("File deletion failed:", error);
      return false;
    }
  }
}

// Re-export ChatFileRef from websocket for convenience
export type { ChatFileRef } from "@/infrastructure/websocket/ChatWebSocket";

/**
 * Convert upload responses to chat file references
 */
export function toChatFileRefs(responses: FileUploadResponse[]): ChatFileRef[] {
  return responses.map((r) => ({
    file_id: r.file_id,
    filename: r.filename,
    mimetype: r.mimetype,
    extracted_content: r.extracted_content,
  }));
}
