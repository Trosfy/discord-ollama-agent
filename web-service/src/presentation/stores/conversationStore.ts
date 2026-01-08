/**
 * Conversation Store
 *
 * Zustand store for managing chat conversations.
 * Persists to localStorage.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface Conversation {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  archived: boolean;
  pinned?: boolean;
  messages?: unknown[];
}

interface ConversationState {
  conversations: Conversation[];
  currentConversationId: string | null;

  // Actions
  addConversation: (conversation: Conversation) => void;
  updateConversation: (id: string, updates: Partial<Conversation>) => void;
  deleteConversation: (id: string) => void;
  setCurrentConversation: (id: string) => void;
  getConversation: (id: string) => Conversation | undefined;
}

export const useConversationStore = create<ConversationState>()(
  persist(
    (set, get) => ({
      conversations: [],
      currentConversationId: null,

      addConversation: (conversation) =>
        set((state) => ({
          conversations: [conversation, ...state.conversations],
          currentConversationId: conversation.id,
        })),

      updateConversation: (id, updates) =>
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === id ? { ...conv, ...updates, updatedAt: new Date() } : conv
          ),
        })),

      deleteConversation: (id) =>
        set((state) => ({
          conversations: state.conversations.filter((conv) => conv.id !== id),
          currentConversationId:
            state.currentConversationId === id
              ? state.conversations[0]?.id || null
              : state.currentConversationId,
        })),

      setCurrentConversation: (id) =>
        set({ currentConversationId: id }),

      getConversation: (id) =>
        get().conversations.find((conv) => conv.id === id),
    }),
    {
      name: "trollama-conversations",
    }
  )
);
