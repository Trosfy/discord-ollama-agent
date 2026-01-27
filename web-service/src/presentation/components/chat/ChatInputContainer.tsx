/**
 * Chat Input Container Component
 *
 * Self-contained, reusable input component with complete file attachment support.
 * Handles: file picker, drag-and-drop, paste, preview, upload, and cleanup.
 *
 * Usage:
 * <ChatInputContainer
 *   onSend={(content, fileRefs) => sendMessageToBackend(content, fileRefs)}
 *   disabled={isStreaming}
 *   centered // optional, for welcome screen
 * />
 */

"use client";

import { useFileAttachments } from "@/hooks/useFileAttachments";
import { ChatInput } from "./ChatInput";
import { FileAttachment } from "@/domain/types/attachment.types";
import { FileStorageService } from "@/infrastructure/storage/FileStorageService";
import { MessageAttachment } from "./AttachmentBadge";
import { toast } from "sonner";
import { useMemo, useEffect, useState } from "react";
import { useMonitoring } from "@/contexts/MonitoringContext";
import { useSettingsStore } from "@/stores/settingsStore";
import { API_CONFIG } from "@/config/api.config";

interface FileReference {
  file_id: string;
  filename?: string;
  mimetype: string;
  extracted_content?: string;
}

interface ChatInputContainerProps {
  /** Called when user sends a message with uploaded file references and selected model */
  onSend: (content: string, fileRefs: FileReference[], modelId: string) => void | Promise<void>;
  /** Disable input (e.g., while streaming) */
  disabled?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Centered mode for welcome screen */
  centered?: boolean;
}

export function ChatInputContainer({
  onSend,
  disabled = false,
  placeholder = "Reply",
  centered = false,
}: ChatInputContainerProps) {
  // File attachments hook with all drag-drop, paste, and file management
  const {
    attachments,
    addFiles,
    removeAttachment,
    clearAttachments,
    isDragging,
    dragHandlers,
    handlePaste,
    fileInputRef,
    openFilePicker,
    uploadAttachments,
    isUploading,
  } = useFileAttachments({
    maxFileSize: 10 * 1024 * 1024, // 10MB
    maxAttachments: 5,
    onError: (error) => toast.error(error),
  });

  // Fetch all available models from API (Ollama + SGLang)
  const [availableModels, setAvailableModels] = useState<any[]>([]);

  // Get real-time loaded model status from SSE
  const { data } = useMonitoring();
  const loadedModels = data?.vram?.loaded_models || [];

  // Get selected model from persisted settings store
  const { selectedModelId, setSelectedModelId } = useSettingsStore();

  // Fetch all available models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        // Get auth token from localStorage
        const token = localStorage.getItem("trollama_auth_token");
        if (!token) {
          console.warn("No auth token - skipping model fetch");
          return;
        }

        const response = await fetch(API_CONFIG.ENDPOINTS.ADMIN.MODELS.LIST, {
          headers: {
            "Authorization": `Bearer ${token}`,
          },
        });
        if (response.ok) {
          const data = await response.json();
          setAvailableModels(data.models || []);
        }
      } catch (error) {
        console.error("Failed to fetch available models:", error);
      }
    };

    fetchModels();
  }, []);

  // Transform model list to dropdown format
  const models = useMemo(() => {
    // Always include trollama router option at the top
    const trollamaOption = {
      id: "trollama",
      name: "trollama",
      description: "",
      icon: "trollama" as const
    };

    if (availableModels.length === 0) {
      // Fallback: Just show Trollama option
      return [trollamaOption];
    }

    // Transform all available models with real-time loaded status
    const modelList = availableModels.map(model => {
      const shortName = model.name.split('/').pop() || model.name;

      // Check if model is currently loaded (from SSE)
      const isLoaded = loadedModels.some(loaded => loaded.name === model.name);
      const statusColor = isLoaded ? "bg-green-500" : "bg-gray-400";

      return {
        id: model.name,
        name: shortName,
        description: "",
        status: statusColor,
        icon: "default" as const
      };
    }).sort((a, b) => a.name.localeCompare(b.name)); // Sort alphabetically by name

    // Prepend trollama option (stays at top)
    return [trollamaOption, ...modelList];
  }, [availableModels, loadedModels]);

  // Update selected model if it becomes unavailable
  // Only run this check after availableModels are loaded to prevent resetting before API fetch completes
  useEffect(() => {
    if (availableModels.length > 0 && models.length > 0 && !models.find(m => m.id === selectedModelId)) {
      setSelectedModelId("trollama"); // Default to Trollama router
    }
  }, [models, selectedModelId, setSelectedModelId, availableModels.length]);

  const handleSendMessage = async (content: string, messageAttachments?: FileAttachment[]) => {
    // Store attachments in IndexedDB for local preview
    if (messageAttachments && messageAttachments.length > 0) {
      for (const attachment of messageAttachments) {
        try {
          await FileStorageService.storeFile(
            attachment.id,
            attachment.file,
            attachment.name,
            24 // 24 hour TTL
          );
        } catch (error) {
          console.error("Failed to store file in IndexedDB:", error);
        }
      }
    }

    // Upload attachments to backend
    let fileRefs: FileReference[] = [];
    if (messageAttachments && messageAttachments.length > 0) {
      try {
        fileRefs = await uploadAttachments();
        if (fileRefs.length === 0 && messageAttachments.length > 0) {
          toast.error("Failed to upload attachments");
          return;
        }
        toast.success(`Uploaded ${fileRefs.length} file(s)`);
      } catch (error) {
        toast.error("Failed to upload attachments");
        return;
      }
    }

    // Clear attachments
    clearAttachments();

    // Call parent's onSend with content, file references, and selected model
    await onSend(content || "Please analyze the attached file(s).", fileRefs, selectedModelId);
  };

  return (
    <>
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files) {
            addFiles(e.target.files);
            e.target.value = ""; // Reset for same file re-selection
          }
        }}
      />

      {/* Chat input with attachment support */}
      <ChatInput
        onSend={handleSendMessage}
        disabled={disabled || isUploading}
        placeholder={placeholder}
        centered={centered}
        attachments={attachments}
        onRemoveAttachment={removeAttachment}
        onOpenFilePicker={openFilePicker}
        onPaste={handlePaste}
        isDragging={isDragging}
        dragHandlers={dragHandlers}
        models={models}
        selectedModelId={selectedModelId}
        onModelSelect={setSelectedModelId}
      />
    </>
  );
}
