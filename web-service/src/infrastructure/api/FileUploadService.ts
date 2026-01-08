/**
 * File Upload Service
 *
 * Infrastructure service for uploading files to the backend.
 * Follows SOLID principles - Single Responsibility for file uploads.
 */

import { httpClient } from "./HttpClient";
import { FileAttachment } from "@/domain/types/attachment.types";
import { ChatFileRef } from "@/infrastructure/websocket/ChatWebSocket";

/**
 * Response from backend for a single uploaded file
 */
export interface FileUploadResponse {
  file_id: string;
  filename: string;
  content_type: string;
  size: number;
  extracted_content?: string;
  url: string;
  status: "success" | "error";
  error?: string;
}

/**
 * Response from backend for multi-file upload
 */
export interface MultiFileUploadResponse {
  success: boolean;
  file_refs: FileUploadResponse[];
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
}

/**
 * File Upload Service
 */
export class FileUploadService {
  private static readonly UPLOAD_ENDPOINT = "/api/files/upload";
  private static readonly MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

  /**
   * Upload a single file to the backend
   */
  static async uploadFile(
    attachment: FileAttachment,
    options?: UploadOptions
  ): Promise<FileUploadResponse> {
    const result = await this.uploadFiles([attachment], options);
    
    if (result.file_refs.length > 0) {
      return result.file_refs[0];
    }
    
    if (result.errors.length > 0) {
      return {
        file_id: "",
        filename: attachment.name,
        content_type: attachment.mimeType,
        size: attachment.size,
        url: "",
        status: "error",
        error: result.errors[0].error,
      };
    }
    
    throw new Error("Unknown upload error");
  }

  /**
   * Upload multiple files to the backend
   */
  static async uploadFiles(
    attachments: FileAttachment[],
    options?: UploadOptions
  ): Promise<MultiFileUploadResponse> {
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
    
    // Add user ID (could be enhanced to use actual user ID from auth)
    formData.append("user_id", "webui_user");

    try {
      const response = await httpClient.post<MultiFileUploadResponse>(
        this.UPLOAD_ENDPOINT,
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

      return response.data;
    } catch (error) {
      console.error("File upload failed:", error);
      
      // Return error response
      return {
        success: false,
        file_refs: [],
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
      await httpClient.delete(`/api/files/${fileId}`);
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
  return responses
    .filter((r) => r.status === "success")
    .map((r) => ({
      file_id: r.file_id,
      filename: r.filename,
      content_type: r.content_type,
      extracted_content: r.extracted_content,
    }));
}
