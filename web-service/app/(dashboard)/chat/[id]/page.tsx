"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { ChatMessage, Message } from "@/components/chat/ChatMessage";
import { ChatInputContainer } from "@/components/chat/ChatInputContainer";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { WelcomeScreen } from "@/components/chat/WelcomeScreen";
import { useChatStream } from "@/hooks/useChatStream";
import { useConversationStore } from "@/stores/conversationStore";
import { HistoryMessage } from "@/infrastructure/websocket/ChatWebSocket";
import { Toaster, toast } from "sonner";
import { ArrowDown } from "lucide-react";
import { Message as DomainMessage } from "@/domain/entities/Conversation";

export default function ChatPage() {
  const params = useParams();
  const router = useRouter();
  const conversationId = (params?.id as string) || "new";

  // Use conversationStore as single source of truth for messages
  const {
    conversations,
    addConversation,
    updateConversation,
    deleteConversation,
    getConversation,
    setCurrentConversation,
    addMessage,
    setMessages: setStoreMessages,
    deleteMessage: deleteStoreMessage,
  } = useConversationStore();

  // Derive messages from conversationStore
  const conversation = getConversation(conversationId);
  const messages: Message[] = useMemo(() => {
    return (conversation?.messages || []).map((msg: DomainMessage) => ({
      id: msg.id,
      role: msg.role,
      content: msg.content,
      timestamp: typeof msg.timestamp === "string" ? new Date(msg.timestamp) : msg.timestamp,
      tokensUsed: msg.tokensUsed,
      outputTokens: (msg as any).outputTokens,
      totalTokensGenerated: (msg as any).totalTokensGenerated,
      model: msg.model,
      generationTime: (msg as any).generationTime,
    }));
  }, [conversation?.messages]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const userHasScrolledUp = useRef(false); // Track if user has manually scrolled up (for scroll logic)
  const [showScrollButton, setShowScrollButton] = useState(false); // Track if scroll button should be visible (for rendering)
  const [streamingModelName, setStreamingModelName] = useState<string | null>(null); // Track model being used for current stream
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null); // Track which message is being edited

  // Handle session start - sync frontend conversation ID with backend session ID
  const handleSessionStart = useCallback((backendSessionId: string) => {
    // If backend returned a different session ID, update our conversation to match
    if (backendSessionId && backendSessionId !== conversationId) {
      console.log(`[ChatPage] Syncing session ID: ${conversationId} → ${backendSessionId}`);

      // Get current conversation data
      const conversation = getConversation(conversationId);
      if (conversation) {
        // Create new conversation with backend's session ID, preserving data
        const syncedConversation = {
          ...conversation,
          id: backendSessionId,
        };

        // Delete old conversation and add synced one
        deleteConversation(conversationId);
        addConversation(syncedConversation);
        setCurrentConversation(backendSessionId);
      }

      // Navigate to new URL with backend session ID (replace to avoid history issues)
      router.replace(`/chat/${backendSessionId}`);
    }
  }, [conversationId, getConversation, deleteConversation, addConversation, setCurrentConversation, router]);

  // Handle history loaded from backend - save to conversationStore
  const handleHistoryLoaded = useCallback((historyMessages: HistoryMessage[]) => {
    if (historyMessages.length > 0) {
      const loadedMessages: DomainMessage[] = historyMessages.map((msg) => ({
        id: msg.id,
        role: msg.role as "user" | "assistant" | "system",
        content: msg.content,
        timestamp: new Date(msg.timestamp).toISOString(),
        tokensUsed: msg.tokensUsed,
        outputTokens: msg.outputTokens,
        totalTokensGenerated: msg.totalTokensGenerated,
        model: msg.model,
        generationTime: msg.generationTime,
      }));
      setStoreMessages(conversationId, loadedMessages);
      console.log(`[ChatPage] Loaded ${loadedMessages.length} messages from history to store`);
    }
  }, [conversationId, setStoreMessages]);

  // WebSocket streaming
  const {
    isConnected,
    isStreaming,
    isLoadingHistory,
    streamingContent,
    tokensUsed,
    outputTokens,
    totalTokensGenerated,
    generationTime,
    modelUsed,
    sendMessage,
    resetStream,
  } = useChatStream({
    conversationId,
    onSessionStart: handleSessionStart,
    onError: (error) => {
      toast.error(`Connection error: ${error}`);
    },
    onHistoryLoaded: handleHistoryLoaded,
  });

  // Check if user is near bottom of scroll
  const isNearBottom = useCallback(() => {
    const container = messagesContainerRef.current;
    if (!container) return true;

    const threshold = 150; // pixels from bottom
    const position = container.scrollHeight - container.scrollTop - container.clientHeight;
    return position < threshold;
  }, []);

  // Handle scroll events to detect if user scrolls up
  const handleScroll = useCallback(() => {
    const hasScrolledUp = !isNearBottom();
    userHasScrolledUp.current = hasScrolledUp; // Update ref (synchronous for scroll logic)
    setShowScrollButton(hasScrolledUp); // Update state (triggers re-render for button visibility)
  }, [isNearBottom]);

  // Smart auto-scroll: only scroll if user hasn't manually scrolled up
  const scrollToBottom = useCallback((force = false) => {
    if (force || !userHasScrolledUp.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  // Auto-scroll when messages change, but only if user is at bottom
  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, scrollToBottom]);

  // When streaming completes, add the message to conversationStore
  useEffect(() => {
    if (!isStreaming && streamingContent && (tokensUsed !== null || outputTokens !== null)) {
      const assistantMessage: DomainMessage = {
        id: Date.now().toString(),
        role: "assistant",
        content: streamingContent,
        timestamp: new Date().toISOString(),
        tokensUsed: tokensUsed ?? undefined,
        outputTokens: outputTokens ?? undefined,
        totalTokensGenerated: totalTokensGenerated ?? undefined,
        generationTime: generationTime ?? undefined,
        model: modelUsed || undefined,
      };

      addMessage(conversationId, assistantMessage);
      resetStream();
      setStreamingModelName(null);
    }
  }, [isStreaming, streamingContent, tokensUsed, outputTokens, totalTokensGenerated, generationTime, modelUsed, resetStream, conversationId, addMessage]);

  const handleSendMessage = async (
    content: string,
    fileRefs: Array<{ file_id: string; filename?: string; mimetype: string; extracted_content?: string }>,
    modelId: string
  ) => {
    // Build display content
    let displayContent = content;
    if (fileRefs.length > 0 && !content) {
      const attachmentNames = fileRefs.map(f => f.filename || "file").join(", ");
      displayContent = `[Attached: ${attachmentNames}]`;
    }

    // Add user message to conversationStore
    const userMessage: DomainMessage = {
      id: Date.now().toString(),
      role: "user",
      content: displayContent,
      timestamp: new Date().toISOString(),
    };

    addMessage(conversationId, userMessage);

    // Update conversation title from first message if still "New Chat"
    const currentConv = getConversation(conversationId);
    if (currentConv && currentConv.title === "New Chat" && messages.length === 0) {
      const title = displayContent.length > 50 ? displayContent.substring(0, 50) + "..." : displayContent;
      updateConversation(conversationId, { title });
    }

    // Send via WebSocket
    // If "trollama" is selected, send undefined to let router decide
    // Otherwise, send the specific model ID to bypass router
    if (isConnected) {
      const modelToSend = modelId === "trollama" ? undefined : modelId;

      // Set the streaming model name to display during streaming
      // Extract short name (remove provider prefix like "openai/")
      let displayModelName: string | null = null;
      if (modelId !== "trollama") {
        const shortName = modelId.split('/').pop() || modelId;
        displayModelName = shortName;
      }
      setStreamingModelName(displayModelName);

      sendMessage(content || "Please analyze the attached file(s).", fileRefs, modelToSend);
    } else {
      toast.error("Not connected to chat server");
    }
  };

  const handleNewChat = () => {
    // Check if there's already an empty "New Chat" conversation
    const emptyNewChat = conversations.find(
      (conv) =>
        conv.title === "New Chat" &&
        !conv.archived &&
        (!conv.messages || conv.messages.length === 0)
    );

    if (emptyNewChat) {
      // Reuse existing empty conversation
      setCurrentConversation(emptyNewChat.id);
      router.push(`/chat/${emptyNewChat.id}`);
    } else {
      // Create new conversation with empty messages array
      const newConversation = {
        id: Date.now().toString(),
        title: "New Chat",
        createdAt: new Date(),
        updatedAt: new Date(),
        archived: false,
        messages: [],
      };
      addConversation(newConversation);
      router.push(`/chat/${newConversation.id}`);
    }
  };

  const handleCopy = (messageId: string) => {
    toast.success("Message copied to clipboard");
  };

  const handleRegenerate = (messageId: string) => {
    // Find the last user message before this assistant message
    const messageIndex = messages.findIndex((m) => m.id === messageId);
    const lastUserMessage = messages
      .slice(0, messageIndex)
      .reverse()
      .find((m) => m.role === "user");

    if (lastUserMessage) {
      // Remove the assistant message and regenerate
      deleteStoreMessage(conversationId, messageId);
      sendMessage(lastUserMessage.content);
    }
  };

  const handleDelete = (messageId: string) => {
    deleteStoreMessage(conversationId, messageId);
    toast.success("Message deleted");
  };

  const handleStartEdit = (messageId: string) => {
    setEditingMessageId(messageId);
  };

  const handleCancelEdit = () => {
    setEditingMessageId(null);
  };

  const handleEdit = (messageId: string, newContent: string) => {
    // Find message index
    const messageIndex = messages.findIndex((m) => m.id === messageId);

    if (messageIndex === -1) return;

    // Get messages to keep (up to but not including the edited one)
    const messagesToKeep = messages.slice(0, messageIndex);

    // Create the updated message
    const editedMessage: DomainMessage = {
      id: messages[messageIndex].id,
      role: messages[messageIndex].role,
      content: newContent,
      timestamp: new Date().toISOString(),
    };

    // Update store: set messages to kept ones plus edited
    const updatedMessages: DomainMessage[] = [
      ...messagesToKeep.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: typeof m.timestamp === "string" ? m.timestamp : m.timestamp.toISOString(),
        tokensUsed: m.tokensUsed,
        model: m.model,
      })),
      editedMessage,
    ];
    setStoreMessages(conversationId, updatedMessages);
    setEditingMessageId(null);

    // Send edited message to get new AI response
    if (isConnected) {
      sendMessage(newContent);
      toast.success("Message edited", {
        description: "Conversation branched from this point. Subsequent messages have been removed.",
      });
    } else {
      toast.error("Not connected to chat server");
    }
  };

  return (
    <>
      <div className="flex flex-col h-full">
        {/* Loading History */}
        {isLoadingHistory && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-3" />
              <span className="text-sm text-muted-foreground">Loading conversation...</span>
            </div>
          </div>
        )}

        {/* Welcome Screen (when no messages and not loading) - includes centered input */}
        {!isLoadingHistory && messages.length === 0 && !isStreaming && (
          <WelcomeScreen
            onSendMessage={handleSendMessage}
            disabled={!isConnected}
          />
        )}

        {/* Chat View (when there are messages) */}
        {(messages.length > 0 || isStreaming) && (
          <>
            <div className="flex-1 relative">
              {/* Messages Area */}
              <div
                ref={messagesContainerRef}
                onScroll={handleScroll}
                className="absolute inset-0 overflow-y-auto scrollbar-thin"
              >
                {/* Connection Status */}
                {!isConnected && (
                  <div className="text-center py-2">
                    <span className="text-xs text-yellow-500 bg-yellow-500/10 px-3 py-1 rounded-full">
                      Connecting to chat server...
                    </span>
                  </div>
                )}

                <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
                  {messages.map((message) => (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      onCopy={() => handleCopy(message.id)}
                      onRegenerate={
                        message.role === "assistant"
                          ? () => handleRegenerate(message.id)
                          : undefined
                      }
                      onDelete={() => handleDelete(message.id)}
                      onEdit={handleEdit}
                      onStartEdit={
                        message.role === "user" && !isStreaming
                          ? () => handleStartEdit(message.id)
                          : undefined
                      }
                      isEditing={editingMessageId === message.id}
                      onCancelEdit={handleCancelEdit}
                    />
                  ))}

                  {/* Streaming Message */}
                  {isStreaming && (
                    <TypingIndicator
                      content={streamingContent}
                      showDots={!streamingContent}
                      modelName={streamingModelName || modelUsed || undefined}
                    />
                  )}

                  {/* Scroll anchor */}
                  <div ref={messagesEndRef} />
                </div>
              </div>

              {/* Scroll to bottom button - appears when user scrolls up */}
              {showScrollButton && (
                <div className="absolute bottom-2 left-0 right-0 z-30 pointer-events-none">
                  <div className="max-w-3xl mx-auto px-4 flex justify-center">
                    <button
                      onClick={() => {
                        userHasScrolledUp.current = false;
                        setShowScrollButton(false);
                        scrollToBottom(true);
                      }}
                      className="pointer-events-auto p-3 rounded-full backdrop-blur-xl bg-background/30 hover:bg-background/50 border border-white/20 text-foreground shadow-2xl transition-all duration-200 hover:scale-110 ring-1 ring-white/10"
                      aria-label="Scroll to bottom"
                    >
                      <ArrowDown className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Input Area - sticky at bottom of container */}
            <div className="sticky bottom-0 z-20 bg-background pb-6 px-3">
              <ChatInputContainer
                onSend={handleSendMessage}
                disabled={isStreaming || !isConnected}
              />
            </div>
          </>
        )}
      </div>

      {/* Toast Notifications */}
      <Toaster position="bottom-right" theme="dark" />
    </>
  );
}
