"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useConversationStore } from "@/stores/conversationStore";

/**
 * Chat Index Page
 *
 * Redirects to the most recent conversation or creates a new one.
 */
export default function ChatIndexPage() {
  const router = useRouter();
  const { conversations, addConversation } = useConversationStore();

  useEffect(() => {
    // If there are existing conversations, redirect to the most recent one
    if (conversations.length > 0) {
      const mostRecent = conversations[0];
      router.replace(`/chat/${mostRecent.id}`);
    } else {
      // Create a new conversation with empty messages array
      const newConversation = {
        id: Date.now().toString(),
        title: "New Chat",
        createdAt: new Date(),
        updatedAt: new Date(),
        archived: false,
        messages: [],
      };

      addConversation(newConversation);
      router.replace(`/chat/${newConversation.id}`);
    }
  }, [conversations, addConversation, router]);

  // Show loading state while redirecting
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
        <p className="mt-4 text-sm text-muted-foreground">Loading chat...</p>
      </div>
    </div>
  );
}
