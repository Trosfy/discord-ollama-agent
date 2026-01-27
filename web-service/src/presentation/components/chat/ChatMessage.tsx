/**
 * ChatMessage Component
 *
 * Clean message layout following Open WebUI style:
 * - No avatars/badges
 * - Model name above assistant messages
 * - Action icons shown directly at bottom
 * - Attachment badges for user messages with files
 */

"use client";

import { useState } from "react";
import { MessageContent } from "./MessageContent";
import { AttachmentBadges, MessageAttachment } from "./AttachmentBadge";
import { Button } from "@/components/ui/button";
import {
  Copy,
  RefreshCw,
  Check,
  Edit2,
  X,
  Send,
} from "lucide-react";

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  tokensUsed?: number;
  outputTokens?: number;  // Visible output tokens (for display)
  totalTokensGenerated?: number;  // Total tokens including thinking (for TPS)
  generationTime?: number; // seconds
  model?: string;
  attachments?: MessageAttachment[];
}

interface ChatMessageProps {
  message: Message;
  onCopy?: () => void;
  onRegenerate?: () => void;
  onDelete?: () => void;
  onEdit?: (messageId: string, newContent: string) => void;
  onStartEdit?: () => void;
  isEditing?: boolean;
  onCancelEdit?: () => void;
  showActions?: boolean;
}

export function ChatMessage({
  message,
  onCopy,
  onRegenerate,
  onEdit,
  onStartEdit,
  isEditing = false,
  onCancelEdit,
  showActions = true,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const isUser = message.role === "user";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      onCopy?.();
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleSaveEdit = () => {
    if (editContent.trim() && onEdit) {
      onEdit(message.id, editContent.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      onCancelEdit?.();
    }
  };

  // User message - simple right-aligned bubble with attachment badges
  if (isUser) {
    // Edit mode
    if (isEditing) {
      return (
        <div className="flex justify-end mb-4">
          <div className="max-w-[85%] md:max-w-[70%] w-full">
            <div className="bg-[#2f2f2f] rounded-3xl p-3">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full min-h-[100px] bg-[#1a1a1a] text-white rounded-xl px-4 py-3 text-[15px] resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                autoFocus
              />
              <div className="flex items-center gap-2 mt-2 justify-end">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onCancelEdit}
                  className="text-white hover:bg-[#1a1a1a]"
                >
                  <X className="w-4 h-4 mr-1" />
                  Cancel
                </Button>
                <Button
                  variant="default"
                  size="sm"
                  onClick={handleSaveEdit}
                  className="bg-primary hover:bg-primary/90"
                >
                  <Send className="w-4 h-4 mr-1" />
                  Save & Send
                </Button>
              </div>
              <p className="text-xs text-gray-400 mt-2">
                Tip: Press <kbd className="px-1.5 py-0.5 bg-[#1a1a1a] rounded text-xs">Ctrl+Enter</kbd> to save
              </p>
            </div>
          </div>
        </div>
      );
    }

    // Normal view mode
    return (
      <div className="group flex justify-end mb-4">
        <div className="max-w-[85%] md:max-w-[70%]">
          <div className="bg-[#2f2f2f] text-white rounded-3xl px-5 py-3 relative">
            <p className="text-[15px] whitespace-pre-wrap break-words">{message.content}</p>
            {/* Attachment badges */}
            {message.attachments && message.attachments.length > 0 && (
              <AttachmentBadges attachments={message.attachments} size="sm" />
            )}
            {/* Edit button - shown on hover */}
            {showActions && onStartEdit && (
              <button
                onClick={onStartEdit}
                className="absolute -left-8 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-[#3f3f3f] rounded-full"
                title="Edit message"
              >
                <Edit2 className="w-4 h-4 text-gray-400" />
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Assistant message - full width with model name and actions
  return (
    <div className="mb-6">
      {/* Model name - Muted metadata styling */}
      <div className="text-muted-foreground text-sm font-medium mb-2">
        {message.model || "trollama"}
      </div>

      {/* Message content */}
      <div className="text-[15px] leading-relaxed prose prose-invert max-w-none">
        <MessageContent content={message.content} role={message.role} />
      </div>

      {/* Action bar - compact icons like Open WebUI */}
      {showActions && (
        <div className="flex items-center gap-4 mt-2 text-muted-foreground/70 text-xs">
          {/* Action icons - Direct clickable SVGs */}
          {copied ? (
            <Check className="h-4 w-4 text-green-500" />
          ) : (
            <Copy
              onClick={handleCopy}
              className="h-4 w-4 cursor-pointer hover:text-foreground transition-colors"
            />
          )}

          {onRegenerate && (
            <RefreshCw
              onClick={onRegenerate}
              className="h-4 w-4 cursor-pointer hover:text-foreground transition-colors"
            />
          )}

          {/* Token metrics */}
          {message.outputTokens && (
            <span className="text-muted-foreground/50">
              {message.outputTokens} tokens
              {message.generationTime && message.totalTokensGenerated && (
                <> · {(message.totalTokensGenerated / message.generationTime).toFixed(1)} t/s</>
              )}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
