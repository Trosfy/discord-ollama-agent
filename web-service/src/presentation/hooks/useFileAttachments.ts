/**
 * useFileAttachments Hook
 * 
 * Manages file attachments state and operations.
 * Follows Single Responsibility - only handles attachment logic.
 * 
 * Features:
 * - Add files from file input, paste, or drag & drop
 * - Remove attachments
 * - Clear all attachments
 * - File validation (size, type)
 * - Upload files to backend
 */

import { useState, useCallback, useRef } from "react";
import { 
  FileAttachment, 
  createFileAttachment 
} from "@/domain/types/attachment.types";
import { 
  FileUploadService, 
  ChatFileRef, 
  toChatFileRefs 
} from "@/infrastructure/api/FileUploadService";

interface UseFileAttachmentsOptions {
  /** Maximum file size in bytes (default: 10MB) */
  maxFileSize?: number;
  /** Maximum number of attachments (default: 5) */
  maxAttachments?: number;
  /** Allowed MIME types (default: all) */
  allowedTypes?: string[];
  /** Callback when validation fails */
  onError?: (error: string) => void;
}

interface UseFileAttachmentsReturn {
  /** Current attachments */
  attachments: FileAttachment[];
  /** Add files to attachments */
  addFiles: (files: FileList | File[]) => void;
  /** Remove an attachment by ID */
  removeAttachment: (id: string) => void;
  /** Clear all attachments */
  clearAttachments: () => void;
  /** Check if dragging over */
  isDragging: boolean;
  /** Drag event handlers */
  dragHandlers: {
    onDragEnter: (e: React.DragEvent) => void;
    onDragLeave: (e: React.DragEvent) => void;
    onDragOver: (e: React.DragEvent) => void;
    onDrop: (e: React.DragEvent) => void;
  };
  /** Paste handler */
  handlePaste: (e: React.ClipboardEvent) => void;
  /** File input ref */
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  /** Open file picker */
  openFilePicker: () => void;
  /** Upload all pending attachments and return file refs for chat */
  uploadAttachments: () => Promise<ChatFileRef[]>;
  /** Whether upload is in progress */
  isUploading: boolean;
}

const DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const DEFAULT_MAX_ATTACHMENTS = 5;

export function useFileAttachments(
  options: UseFileAttachmentsOptions = {}
): UseFileAttachmentsReturn {
  const {
    maxFileSize = DEFAULT_MAX_FILE_SIZE,
    maxAttachments = DEFAULT_MAX_ATTACHMENTS,
    allowedTypes,
    onError,
  } = options;

  const [attachments, setAttachments] = useState<FileAttachment[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);

  /**
   * Validates a file before adding
   */
  const validateFile = useCallback((file: File): string | null => {
    // Check file size
    if (file.size > maxFileSize) {
      return `File "${file.name}" is too large. Maximum size is ${Math.round(maxFileSize / 1024 / 1024)}MB.`;
    }

    // Check file type
    if (allowedTypes && allowedTypes.length > 0) {
      const isAllowed = allowedTypes.some(type => {
        if (type.endsWith("/*")) {
          return file.type.startsWith(type.replace("/*", "/"));
        }
        return file.type === type;
      });
      if (!isAllowed) {
        return `File type "${file.type || "unknown"}" is not allowed.`;
      }
    }

    return null;
  }, [maxFileSize, allowedTypes]);

  /**
   * Add files to attachments
   */
  const addFiles = useCallback((files: FileList | File[]) => {
    const fileArray = Array.from(files);
    
    setAttachments((prev) => {
      // Check max attachments
      const remaining = maxAttachments - prev.length;
      if (remaining <= 0) {
        onError?.(`Maximum ${maxAttachments} attachments allowed.`);
        return prev;
      }

      const filesToAdd = fileArray.slice(0, remaining);
      const newAttachments: FileAttachment[] = [];

      for (const file of filesToAdd) {
        const error = validateFile(file);
        if (error) {
          onError?.(error);
          continue;
        }
        newAttachments.push(createFileAttachment(file));
      }

      if (fileArray.length > remaining) {
        onError?.(`Only ${remaining} more file(s) can be added.`);
      }

      return [...prev, ...newAttachments];
    });
  }, [maxAttachments, validateFile, onError]);

  /**
   * Remove an attachment by ID
   */
  const removeAttachment = useCallback((id: string) => {
    setAttachments((prev) => {
      const attachment = prev.find(a => a.id === id);
      // Revoke blob URL to prevent memory leaks
      if (attachment?.previewUrl) {
        URL.revokeObjectURL(attachment.previewUrl);
      }
      return prev.filter(a => a.id !== id);
    });
  }, []);

  /**
   * Clear all attachments
   */
  const clearAttachments = useCallback(() => {
    setAttachments((prev) => {
      // Revoke all blob URLs
      prev.forEach(a => {
        if (a.previewUrl) {
          URL.revokeObjectURL(a.previewUrl);
        }
      });
      return [];
    });
  }, []);

  /**
   * Handle paste event (for pasting images)
   */
  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    const files: File[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) {
          files.push(file);
        }
      }
    }

    if (files.length > 0) {
      e.preventDefault();
      addFiles(files);
    }
  }, [addFiles]);

  /**
   * Drag and drop handlers
   */
  const onDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer?.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    dragCounterRef.current = 0;

    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      addFiles(files);
    }
  }, [addFiles]);

  /**
   * Open file picker dialog
   */
  const openFilePicker = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  /**
   * Upload all pending attachments to the backend
   * Returns file references for sending with chat message
   */
  const uploadAttachments = useCallback(async (): Promise<ChatFileRef[]> => {
    const pendingAttachments = attachments.filter(
      (a) => a.status === "pending"
    );
    
    if (pendingAttachments.length === 0) {
      return [];
    }

    setIsUploading(true);

    // Update status to uploading
    setAttachments((prev) =>
      prev.map((a) =>
        pendingAttachments.some((p) => p.id === a.id)
          ? { ...a, status: "uploading" as const }
          : a
      )
    );

    try {
      const result = await FileUploadService.uploadFiles(
        pendingAttachments,
        {
          onProgress: (progress) => {
            // Update progress for all uploading files
            setAttachments((prev) =>
              prev.map((a) =>
                a.status === "uploading" ? { ...a, progress } : a
              )
            );
          },
        }
      );

      // Update attachment statuses based on result
      setAttachments((prev) =>
        prev.map((a) => {
          const fileRef = result.file_refs.find(
            (r) => r.filename === a.name
          );
          const error = result.errors.find(
            (e) => e.filename === a.name
          );

          if (fileRef) {
            return {
              ...a,
              status: "uploaded" as const,
              progress: 100,
              remoteUrl: fileRef.url,
            };
          } else if (error) {
            return {
              ...a,
              status: "error" as const,
              error: error.error,
            };
          }
          return a;
        })
      );

      // Return file refs for chat
      return toChatFileRefs(result.file_refs);
    } catch (error) {
      // Mark all as error
      setAttachments((prev) =>
        prev.map((a) =>
          a.status === "uploading"
            ? {
                ...a,
                status: "error" as const,
                error: error instanceof Error ? error.message : "Upload failed",
              }
            : a
        )
      );
      onError?.(error instanceof Error ? error.message : "Upload failed");
      return [];
    } finally {
      setIsUploading(false);
    }
  }, [attachments, onError]);

  return {
    attachments,
    addFiles,
    removeAttachment,
    clearAttachments,
    isDragging,
    dragHandlers: {
      onDragEnter,
      onDragLeave,
      onDragOver,
      onDrop,
    },
    handlePaste,
    fileInputRef,
    openFilePicker,
    uploadAttachments,
    isUploading,
  };
}
