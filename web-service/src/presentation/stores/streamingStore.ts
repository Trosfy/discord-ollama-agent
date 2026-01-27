/**
 * Streaming Store
 *
 * Zustand store for managing streaming state during chat responses.
 * Message storage lives in conversationStore - this handles only transient streaming state.
 */

import { create } from "zustand";

interface StreamingState {
  // State
  isStreaming: boolean;
  streamingContent: string;
  activeConversationId: string | null;
  pendingMessageId: string | null;

  // Streaming Actions
  setStreaming: (isStreaming: boolean) => void;
  appendStreamingContent: (chunk: string) => void;
  clearStreamingContent: () => void;
  setActiveConversationId: (id: string | null) => void;
  setPendingMessageId: (id: string | null) => void;

  // Reset all streaming state
  resetStreaming: () => void;
}

export const useStreamingStore = create<StreamingState>((set) => ({
  // Initial State
  isStreaming: false,
  streamingContent: "",
  activeConversationId: null,
  pendingMessageId: null,

  // Streaming Actions
  setStreaming: (isStreaming) => set({ isStreaming }),

  appendStreamingContent: (chunk) =>
    set((state) => ({
      streamingContent: state.streamingContent + chunk,
    })),

  clearStreamingContent: () => set({ streamingContent: "" }),

  setActiveConversationId: (id) => set({ activeConversationId: id }),

  setPendingMessageId: (id) => set({ pendingMessageId: id }),

  resetStreaming: () =>
    set({
      isStreaming: false,
      streamingContent: "",
      pendingMessageId: null,
    }),
}));
