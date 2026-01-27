/**
 * Welcome Screen Component - Open WebUI Style
 *
 * Clean, centered layout with personalized greeting and suggested prompts.
 * Model selector is now in the TopBar.
 */

"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { Zap } from "lucide-react";
import { ChatInputContainer } from "./ChatInputContainer";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/authStore";
import { useSettingsStore } from "@/stores/settingsStore";

interface SuggestedPrompt {
  title: string;
  subtitle: string;
  prompt: string;
}

interface FileReference {
  file_id: string;
  filename?: string;
  mimetype: string;
  extracted_content?: string;
}

interface WelcomeScreenProps {
  onSendMessage: (message: string, fileRefs: FileReference[], modelId: string) => void | Promise<void>;
  disabled?: boolean;
  className?: string;
  suggestedPrompts?: SuggestedPrompt[];
}

const defaultPrompts: SuggestedPrompt[] = [
  { title: "Give me ideas", subtitle: "for a weekend project", prompt: "Give me ideas for a weekend coding project" },
  { title: "Show me a code snippet", subtitle: "for a React component", prompt: "Show me a code snippet for a React button component with hover effects" },
  { title: "Explain", subtitle: "how WebSockets work", prompt: "Explain how WebSockets work in simple terms" },
];

const greetings = [
  "Hi",
  "Hello",
  "Hey",
  "Welcome",
  "Greetings",
  "Good to see you",
  "Nice to see you",
];

export function WelcomeScreen({
  onSendMessage,
  disabled = false,
  className,
  suggestedPrompts = defaultPrompts,
}: WelcomeScreenProps) {
  const { user } = useAuthStore();
  const { selectedModelId } = useSettingsStore();
  const [greeting, setGreeting] = useState("");

  // Randomize greeting on mount
  useEffect(() => {
    const randomGreeting = greetings[Math.floor(Math.random() * greetings.length)];
    setGreeting(randomGreeting);
  }, []);

  const displayName = user?.displayName || "there";

  return (
    <div className={cn(
      "flex flex-col items-center h-full px-4",
      className
    )}>
      {/* Spacer to push content toward center */}
      <div className="flex-1 min-h-16" />

      {/* Logo and Greeting - Centered */}
      <div className="flex flex-col items-center mb-6">
        <div className="w-24 h-24 mb-4">
          <Image
            src="/trollama-badge-no-bg.svg"
            alt="Trollama Logo"
            width={96}
            height={96}
            className="w-full h-full object-contain"
            priority
          />
        </div>
        <h1 className="text-2xl font-semibold">
          {greeting}, {displayName}!
        </h1>
      </div>

      {/* Centered Chat Input */}
      <ChatInputContainer
        onSend={onSendMessage}
        disabled={disabled}
        centered
        placeholder="How can I help you today?"
      />

      {/* Suggested Prompts */}
      <div className="mt-6 w-full max-w-md">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
          <Zap className="w-3 h-3" />
          <span>Suggested</span>
        </div>
        <div className="space-y-2">
          {suggestedPrompts.map((prompt, i) => (
            <button
              key={i}
              onClick={() => onSendMessage(prompt.prompt, [], selectedModelId)}
              disabled={disabled}
              className="w-full text-left px-4 py-3 rounded-xl bg-secondary/50 hover:bg-secondary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="font-medium text-sm">{prompt.title}</div>
              <div className="text-xs text-muted-foreground">{prompt.subtitle}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Spacer */}
      <div className="flex-1 min-h-8" />

      {/* Footer hint */}
      <div className="pb-6 text-xs text-muted-foreground text-center">
        Trollama can make mistakes. Consider checking important information.
      </div>
    </div>
  );
}
