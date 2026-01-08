/**
 * Message Store
 *
 * Zustand store for managing chat messages within a conversation.
 * Follows SOLID principles - Single Responsibility for message state.
 */

import { create } from "zustand";

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  tokensUsed?: number;
  model?: string;
}

interface MessageState {
  // State
  messages: Message[];
  isStreaming: boolean;
  streamingContent: string;
  activeConversationId: string | null;

  // Message Actions
  addMessage: (message: Message) => void;
  setMessages: (messages: Message[]) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  deleteMessage: (id: string) => void;
  clearMessages: () => void;

  // Streaming Actions
  setStreaming: (isStreaming: boolean) => void;
  appendStreamingContent: (chunk: string) => void;
  clearStreamingContent: () => void;
  finalizeStreamingMessage: (tokensUsed?: number, model?: string) => void;

  // Conversation Context
  setActiveConversationId: (id: string | null) => void;
}

export const useMessageStore = create<MessageState>((set, get) => ({
  // Initial State
  messages: [],
  isStreaming: false,
  streamingContent: "",
  activeConversationId: null,

  // Message Actions
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),

  setMessages: (messages) => set({ messages }),

  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, ...updates } : msg
      ),
    })),

  deleteMessage: (id) =>
    set((state) => ({
      messages: state.messages.filter((msg) => msg.id !== id),
    })),

  clearMessages: () => set({ messages: [], streamingContent: "", isStreaming: false }),

  // Streaming Actions
  setStreaming: (isStreaming) => set({ isStreaming }),

  appendStreamingContent: (chunk) =>
    set((state) => ({
      streamingContent: state.streamingContent + chunk,
    })),

  clearStreamingContent: () => set({ streamingContent: "" }),

  finalizeStreamingMessage: (tokensUsed, model) => {
    const { streamingContent, addMessage } = get();
    if (streamingContent.trim()) {
      const message: Message = {
        id: `msg-${Date.now()}`,
        role: "assistant",
        content: streamingContent,
        timestamp: new Date().toISOString(),
        tokensUsed,
        model,
      };
      set({
        messages: [...get().messages, message],
        streamingContent: "",
        isStreaming: false,
      });
    } else {
      set({ streamingContent: "", isStreaming: false });
    }
  },

  // Conversation Context
  setActiveConversationId: (id) => set({ activeConversationId: id }),
}));
