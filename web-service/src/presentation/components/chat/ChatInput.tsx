/**
 * Chat Input Component - Open WebUI Style
 *
 * Clean, rounded input with file attachment support.
 * Supports: click to attach, paste images, drag & drop.
 */

"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { IconButton } from "@/presentation/components/ui/IconButton";
import { ArrowUp, Paperclip, ChevronDown, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";
import { FileAttachment } from "@/domain/types/attachment.types";
import { AttachmentPreview } from "./AttachmentPreview";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Model {
  id: string;
  name: string;
  description: string;
  status?: string; // Status indicator color class (e.g., "bg-green-500")
  icon?: "trollama" | "default"; // Icon type: trollama SVG or default CPU icon
}

interface ChatInputProps {
  onSend: (message: string, attachments?: FileAttachment[]) => void;
  disabled?: boolean;
  placeholder?: string;
  /** Centered mode for welcome screen */
  centered?: boolean;
  className?: string;
  /** Attachments state (controlled) */
  attachments?: FileAttachment[];
  /** Called when attachment is removed */
  onRemoveAttachment?: (id: string) => void;
  /** Called when file picker should open */
  onOpenFilePicker?: () => void;
  /** Called on paste (for clipboard files) */
  onPaste?: (e: React.ClipboardEvent) => void;
  /** Drag state */
  isDragging?: boolean;
  /** Drag event handlers */
  dragHandlers?: {
    onDragEnter: (e: React.DragEvent) => void;
    onDragLeave: (e: React.DragEvent) => void;
    onDragOver: (e: React.DragEvent) => void;
    onDrop: (e: React.DragEvent) => void;
  };
  /** Available models */
  models?: Model[];
  /** Selected model ID */
  selectedModelId?: string;
  /** Called when model is selected */
  onModelSelect?: (modelId: string) => void;
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Reply",
  centered = false,
  className,
  attachments = [],
  onRemoveAttachment,
  onOpenFilePicker,
  onPaste,
  isDragging = false,
  dragHandlers,
  models = [],
  selectedModelId,
  onModelSelect,
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [message]);

  const handleSend = () => {
    const trimmed = message.trim();
    const hasContent = trimmed || attachments.length > 0;
    if (!hasContent || disabled) return;

    onSend(trimmed, attachments.length > 0 ? attachments : undefined);
    setMessage("");

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasContent = !!(message.trim() || attachments.length > 0);

  return (
    <div
      className={cn(
        "w-full relative",
        "max-w-md lg:max-w-3xl mx-auto",
        className
      )}
      {...dragHandlers}
    >
      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-2xl border-2 border-dashed border-primary bg-primary/10">
          <div className="text-sm font-medium text-primary">
            Drop files to attach
          </div>
        </div>
      )}

      {/* Attachment previews */}
      {attachments.length > 0 && onRemoveAttachment && (
        <AttachmentPreview 
          attachments={attachments} 
          onRemove={onRemoveAttachment}
        />
      )}

      <div className={cn(
        "border border-border/40 rounded-2xl bg-secondary/30",
        "focus-within:border-border/60",
        "transition-all duration-200",
        attachments.length > 0 ? "rounded-b-2xl border-t-0" : ""
      )}>
        {/* Message Input - on top */}
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={onPaste}
          placeholder={placeholder}
          disabled={disabled}
          className={cn(
            "w-full min-h-[44px] max-h-[200px] py-3 px-4 resize-none",
            "!bg-transparent border-0 focus-visible:ring-0 focus-visible:ring-offset-0",
            "placeholder:text-muted-foreground/60 shadow-none"
          )}
          rows={1}
        />

        {/* Button row - below textarea */}
        <div className="flex items-center justify-between pl-4 pr-2 pb-2">
          {/* Left side - attach button */}
          <div className="flex items-center gap-2">
            {onOpenFilePicker && (
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground transition-colors"
                onClick={onOpenFilePicker}
              >
                <Paperclip className="h-5 w-5" />
                <span className="sr-only">Attach file</span>
              </button>
            )}
          </div>

          {/* Right side - model selector and send button */}
          <div className="flex items-center gap-2">
            {/* Model Selector (Display Only - Router Handles Selection) */}
            {models.length > 0 && onModelSelect && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className="flex items-center gap-1.5 px-2 py-1 text-sm text-muted-foreground hover:text-foreground transition-colors rounded-lg hover:bg-secondary/50"
                    title="Available models (routing handled automatically)"
                  >
                    {models.find(m => m.id === selectedModelId)?.icon === "trollama" ? (
                      <img
                        src="/trollama-badge-no-bg.svg"
                        alt="trollama"
                        className="h-4 w-4"
                      />
                    ) : (
                      <Cpu className="h-4 w-4" />
                    )}
                    <span className="font-medium">
                      {models.find(m => m.id === selectedModelId)?.name || models[0]?.name}
                    </span>
                    <ChevronDown className="h-3 w-3" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="end"
                  side={centered ? "bottom" : "top"}
                  className="w-64 max-h-64 overflow-y-auto"
                >
                  {models.map((model) => (
                    <DropdownMenuItem
                      key={model.id}
                      onClick={() => onModelSelect(model.id)}
                      className={cn(
                        "flex items-center gap-3 p-3 cursor-pointer",
                        model.id === selectedModelId && "bg-secondary"
                      )}
                    >
                      <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-primary/80 to-primary flex items-center justify-center shrink-0">
                        {model.icon === "trollama" ? (
                          <img
                            src="/trollama-badge-no-bg.svg"
                            alt="trollama"
                            className="w-4 h-4"
                          />
                        ) : (
                          <Cpu className="w-3 h-3 text-primary-foreground" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm truncate">{model.name}</div>
                      </div>
                      {model.status && (
                        <div className={cn("w-2 h-2 rounded-full shrink-0", model.status)} />
                      )}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}

            {/* Send button */}
            <IconButton
              size="lg"
              active={hasContent}
              disabled={!hasContent || disabled}
              onClick={handleSend}
            >
              <ArrowUp />
              <span className="sr-only">Send message</span>
            </IconButton>
          </div>
        </div>
      </div>
    </div>
  );
}
