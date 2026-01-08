/**
 * AttachmentPreview Component
 * 
 * Displays attached files with preview, filename, size, and remove button.
 * Follows Single Responsibility - only handles attachment display.
 */

"use client";

import { X, FileText, Image as ImageIcon, Film, Music, File } from "lucide-react";
import { IconButton } from "@/presentation/components/ui/IconButton";
import { 
  FileAttachment, 
  formatFileSize 
} from "@/domain/types/attachment.types";
import { cn } from "@/lib/utils";

interface AttachmentPreviewProps {
  attachments: FileAttachment[];
  onRemove: (id: string) => void;
  className?: string;
}

export function AttachmentPreview({ 
  attachments, 
  onRemove,
  className 
}: AttachmentPreviewProps) {
  if (attachments.length === 0) return null;

  return (
    <div className={cn(
      "grid grid-cols-3 gap-2 p-2 bg-secondary/30 rounded-t-xl border-t border-x border-border",
      className
    )}>
      {attachments.map((attachment) => (
        <AttachmentItem 
          key={attachment.id} 
          attachment={attachment} 
          onRemove={onRemove}
        />
      ))}
    </div>
  );
}

interface AttachmentItemProps {
  attachment: FileAttachment;
  onRemove: (id: string) => void;
}

function AttachmentItem({ attachment, onRemove }: AttachmentItemProps) {
  const isImage = attachment.type === "image";

  return (
    <div className="relative group w-full h-24 bg-secondary/50 rounded-lg overflow-visible border border-border">
      {/* Remove button - xs size (1/4 of send button) */}
      <IconButton
        size="xs"
        className="absolute z-10 -top-1.5 -right-1.5"
        onClick={() => onRemove(attachment.id)}
      >
        <X />
      </IconButton>

      {isImage ? (
        // Image preview
        <div className="w-full h-full">
          {attachment.previewUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={attachment.previewUrl}
              alt={attachment.name}
              className="w-full h-full object-cover"
            />
          )}
          {/* Upload status overlay */}
          {attachment.status === "uploading" && (
            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
              <div className="text-xs text-white">{attachment.progress}%</div>
            </div>
          )}
          {attachment.status === "error" && (
            <div className="absolute inset-0 bg-red-500/50 flex items-center justify-center">
              <X className="h-4 w-4 text-white" />
            </div>
          )}
        </div>
      ) : (
        // File preview - centered content
        <div className="w-full h-full flex flex-col items-center justify-center gap-1 px-2">
          <FileTypeIcon type={attachment.type} />
          <span className="text-xs font-medium truncate max-w-full text-center">
            {attachment.name}
          </span>
          <span className="text-[10px] text-muted-foreground">
            {formatFileSize(attachment.size)}
          </span>
        </div>
      )}
    </div>
  );
}

function FileTypeIcon({ type }: { type: FileAttachment["type"] }) {
  const iconClass = "h-5 w-5 text-muted-foreground";
  
  switch (type) {
    case "image":
      return <ImageIcon className={iconClass} />;
    case "video":
      return <Film className={iconClass} />;
    case "audio":
      return <Music className={iconClass} />;
    case "document":
      return <FileText className={iconClass} />;
    default:
      return <File className={iconClass} />;
  }
}
