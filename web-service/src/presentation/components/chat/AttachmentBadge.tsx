/**
 * AttachmentBadge Component
 *
 * Mini clickable badges showing file attachments in messages.
 * Click to open the file from local IndexedDB storage.
 */

"use client";

import { useState } from "react";
import { FileStorageService } from "@/infrastructure/storage/FileStorageService";
import { 
  FileText, 
  Image as ImageIcon, 
  FileAudio, 
  FileVideo, 
  File,
  Download,
  ExternalLink,
  Loader2
} from "lucide-react";
import { toast } from "sonner";

export interface MessageAttachment {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
}

interface AttachmentBadgeProps {
  attachment: MessageAttachment;
  size?: "sm" | "md";
}

/**
 * Get the appropriate icon for a file type
 */
function getFileIcon(mimeType: string) {
  if (mimeType.startsWith("image/")) return ImageIcon;
  if (mimeType.startsWith("video/")) return FileVideo;
  if (mimeType.startsWith("audio/")) return FileAudio;
  if (
    mimeType.includes("pdf") ||
    mimeType.includes("document") ||
    mimeType.includes("text/")
  ) {
    return FileText;
  }
  return File;
}

/**
 * Format file size for display
 */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AttachmentBadge({ attachment, size = "sm" }: AttachmentBadgeProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  
  const Icon = getFileIcon(attachment.mimeType);
  const isImage = attachment.mimeType.startsWith("image/");
  
  const iconSize = size === "sm" ? "h-3 w-3" : "h-4 w-4";
  const textSize = size === "sm" ? "text-[11px]" : "text-xs";
  const padding = size === "sm" ? "px-2 py-1" : "px-3 py-1.5";

  const handleClick = async () => {
    setIsLoading(true);
    
    try {
      // Try to open the file
      const opened = await FileStorageService.openFile(attachment.id);
      
      if (!opened) {
        toast.error("File not found in local storage", {
          description: "The file may have expired (24h TTL)",
        });
      }
    } catch (error) {
      console.error("Failed to open file:", error);
      toast.error("Failed to open file");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(false);
    setIsLoading(true);
    
    try {
      const downloaded = await FileStorageService.downloadFile(attachment.id);
      
      if (!downloaded) {
        toast.error("File not found in local storage", {
          description: "The file may have expired (24h TTL)",
        });
      }
    } catch (error) {
      console.error("Failed to download file:", error);
      toast.error("Failed to download file");
    } finally {
      setIsLoading(false);
    }
  };

  // Truncate filename if too long
  const displayName = attachment.filename.length > 20
    ? attachment.filename.substring(0, 17) + "..."
    : attachment.filename;

  return (
    <div className="relative inline-block">
      <button
        onClick={handleClick}
        onContextMenu={(e) => {
          e.preventDefault();
          setShowMenu(!showMenu);
        }}
        disabled={isLoading}
        className={`
          inline-flex items-center gap-1.5 ${padding} rounded-lg
          bg-primary/10 hover:bg-primary/20 
          text-primary transition-colors
          border border-primary/20
          cursor-pointer disabled:opacity-50
          ${textSize}
        `}
        title={`${attachment.filename} (${formatSize(attachment.size)})`}
      >
        {isLoading ? (
          <Loader2 className={`${iconSize} animate-spin`} />
        ) : (
          <Icon className={iconSize} />
        )}
        <span className="truncate max-w-[120px]">{displayName}</span>
      </button>

      {/* Context menu */}
      {showMenu && (
        <>
          <div 
            className="fixed inset-0 z-40" 
            onClick={() => setShowMenu(false)} 
          />
          <div className="absolute bottom-full left-0 mb-1 z-50 bg-popover border border-border rounded-lg shadow-lg py-1 min-w-[140px]">
            <button
              onClick={handleClick}
              className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 hover:bg-muted"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Open
            </button>
            <button
              onClick={handleDownload}
              className="w-full px-3 py-1.5 text-left text-sm flex items-center gap-2 hover:bg-muted"
            >
              <Download className="h-3.5 w-3.5" />
              Download
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Group of attachment badges
 */
interface AttachmentBadgesProps {
  attachments: MessageAttachment[];
  size?: "sm" | "md";
}

export function AttachmentBadges({ attachments, size = "sm" }: AttachmentBadgesProps) {
  if (!attachments || attachments.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-1.5">
      {attachments.map((attachment) => (
        <AttachmentBadge 
          key={attachment.id} 
          attachment={attachment} 
          size={size}
        />
      ))}
    </div>
  );
}
