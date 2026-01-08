/**
 * TypingIndicator Component
 *
 * Animated typing indicator for assistant messages.
 * Shows streaming content as it arrives.
 * Matches Open WebUI style - no avatar, model name on top.
 */

"use client";

import { useState } from "react";
import { MessageContent } from "./MessageContent";

interface TypingIndicatorProps {
  content?: string;
  showDots?: boolean;
  modelName?: string; // Model name to display during streaming
}

export function TypingIndicator({ content, showDots = true, modelName }: TypingIndicatorProps) {
  const loadingMessages = [
    "thinking...",
    "analyzing request...",
    "selecting best model...",
    "processing query...",
    "routing to specialist...",
    "preparing response...",
  ];

  // Pick random message on mount
  const [randomMessage] = useState(() =>
    loadingMessages[Math.floor(Math.random() * loadingMessages.length)]
  );

  const displayName = modelName || randomMessage;

  return (
    <div className="mb-6">
      {/* Model name - Muted metadata styling */}
      <div className="text-muted-foreground text-sm font-medium mb-2">
        {displayName}
      </div>

      {/* Message content or typing dots */}
      <div className="text-[15px] leading-relaxed prose prose-invert max-w-none">
        {content ? (
          <MessageContent content={content} role="assistant" />
        ) : (
          showDots && <TypingDots />
        )}
      </div>
    </div>
  );
}

/**
 * Animated typing dots
 */
function TypingDots() {
  return (
    <div className="flex gap-1.5 items-center py-2">
      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:-0.3s]" />
      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:-0.15s]" />
      <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
    </div>
  );
}
