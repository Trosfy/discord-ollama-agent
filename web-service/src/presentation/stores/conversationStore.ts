/**
 * Conversation Store
 *
 * Zustand store for managing chat conversations.
 * Persists to localStorage - single source of truth for messages.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { Message } from "@/domain/entities/Conversation";

export interface Conversation {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  archived: boolean;
  pinned?: boolean;
  messages: Message[];
}

interface ConversationState {
  conversations: Conversation[];
  currentConversationId: string | null;

  // Conversation Actions
  addConversation: (conversation: Conversation) => void;
  updateConversation: (id: string, updates: Partial<Conversation>) => void;
  deleteConversation: (id: string) => void;
  setCurrentConversation: (id: string) => void;
  getConversation: (id: string) => Conversation | undefined;

  // Message Actions
  addMessage: (conversationId: string, message: Message) => void;
  setMessages: (conversationId: string, messages: Message[]) => void;
  updateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => void;
  deleteMessage: (conversationId: string, messageId: string) => void;
  getMessages: (conversationId: string) => Message[];
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

      // Message Actions
      addMessage: (conversationId, message) =>
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? { ...conv, messages: [...(conv.messages || []), message], updatedAt: new Date() }
              : conv
          ),
        })),

      setMessages: (conversationId, messages) =>
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? { ...conv, messages, updatedAt: new Date() }
              : conv
          ),
        })),

      updateMessage: (conversationId, messageId, updates) =>
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: (conv.messages || []).map((msg) =>
                    msg.id === messageId ? { ...msg, ...updates } : msg
                  ),
                  updatedAt: new Date(),
                }
              : conv
          ),
        })),

      deleteMessage: (conversationId, messageId) =>
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: (conv.messages || []).filter((msg) => msg.id !== messageId),
                  updatedAt: new Date(),
                }
              : conv
          ),
        })),

      getMessages: (conversationId) =>
        get().conversations.find((conv) => conv.id === conversationId)?.messages || [],
    }),
    {
      name: "trollama-conversations",
    }
  )
);
