/**
 * Attachment Types
 * 
 * Domain types for file attachments in chat.
 * Supports images, documents, and other file types.
 */

export type AttachmentType = "image" | "document" | "audio" | "video" | "other";

export interface FileAttachment {
  /** Unique ID for this attachment */
  id: string;
  /** Original filename */
  name: string;
  /** MIME type */
  mimeType: string;
  /** File size in bytes */
  size: number;
  /** Categorized type */
  type: AttachmentType;
  /** Local preview URL (blob URL for images) */
  previewUrl?: string;
  /** The actual File object */
  file: File;
  /** Upload status */
  status: "pending" | "uploading" | "uploaded" | "error";
  /** Upload progress (0-100) */
  progress: number;
  /** Error message if upload failed */
  error?: string;
  /** Remote URL after upload */
  remoteUrl?: string;
}

export interface AttachmentUploadResult {
  success: boolean;
  remoteUrl?: string;
  error?: string;
}

/**
 * Determines the attachment type from MIME type
 */
export function getAttachmentType(mimeType: string): AttachmentType {
  if (mimeType.startsWith("image/")) return "image";
  if (mimeType.startsWith("video/")) return "video";
  if (mimeType.startsWith("audio/")) return "audio";
  if (
    mimeType.includes("pdf") ||
    mimeType.includes("document") ||
    mimeType.includes("text/") ||
    mimeType.includes("application/json") ||
    mimeType.includes("application/xml")
  ) {
    return "document";
  }
  return "other";
}

/**
 * Creates a FileAttachment from a File object
 */
export function createFileAttachment(file: File): FileAttachment {
  const type = getAttachmentType(file.type);
  const previewUrl = type === "image" ? URL.createObjectURL(file) : undefined;

  // Use alphanumeric-only ID to avoid IndexedDB path issues
  const randomPart = Math.random().toString(36).substring(2, 11);
  return {
    id: `file_${Date.now()}_${randomPart}`,
    name: file.name,
    mimeType: file.type || "application/octet-stream",
    size: file.size,
    type,
    previewUrl,
    file,
    status: "pending",
    progress: 0,
  };
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
