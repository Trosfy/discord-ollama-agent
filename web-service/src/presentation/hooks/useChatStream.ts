/**
 * useChatStream Hook
 *
 * React hook for WebSocket chat streaming.
 * Manages connection, token streaming, and message state.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { ChatWebSocketClient, HistoryMessage, ChatFileRef } from "@/infrastructure/websocket/ChatWebSocket";
import { useSettingsStore } from "@/stores/settingsStore";

interface UseChatStreamOptions {
  conversationId: string;
  onError?: (error: string) => void;
  onCloseComplete?: (deletedCount: number) => void;
  onHistoryLoaded?: (messages: HistoryMessage[]) => void;
}

export function useChatStream({ conversationId, onError, onCloseComplete, onHistoryLoaded }: UseChatStreamOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [tokensUsed, setTokensUsed] = useState<number | null>(null);
  const [outputTokens, setOutputTokens] = useState<number | null>(null);
  const [totalTokensGenerated, setTotalTokensGenerated] = useState<number | null>(null);
  const [generationTime, setGenerationTime] = useState<number | null>(null);
  const [modelUsed, setModelUsed] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  const wsClientRef = useRef<ChatWebSocketClient | null>(null);
  const historyRequestedRef = useRef(false);

  // Store callbacks in refs to avoid reconnections
  const onErrorRef = useRef(onError);
  const onCloseCompleteRef = useRef(onCloseComplete);
  const onHistoryLoadedRef = useRef(onHistoryLoaded);
  useEffect(() => {
    onErrorRef.current = onError;
    onCloseCompleteRef.current = onCloseComplete;
    onHistoryLoadedRef.current = onHistoryLoaded;
  }, [onError, onCloseComplete, onHistoryLoaded]);

  // Initialize WebSocket connection
  useEffect(() => {
    historyRequestedRef.current = false;
    
    const wsClient = new ChatWebSocketClient({
      conversationId,
      onToken: (token) => {
        setStreamingContent((prev) => prev + token);
      },
      onDone: (tokens, genTime, outTokens, totalTokens, model) => {
        setIsStreaming(false);
        setTokensUsed(tokens || null);
        setOutputTokens(outTokens || null);
        setTotalTokensGenerated(totalTokens || null);
        setGenerationTime(genTime || null);
        setModelUsed(model || null);
        console.log(`[useChatStream] Stream complete: ${outTokens || tokens} tokens in ${genTime?.toFixed(2)}s, model: ${model}`);
      },
      onError: (error) => {
        setIsStreaming(false);
        setIsLoadingHistory(false);
        console.error(`[useChatStream] Error:`, error);
        onErrorRef.current?.(error);
      },
      onConnect: () => {
        setIsConnected(true);
        // Request history once connected (only once per conversation)
        if (!historyRequestedRef.current) {
          historyRequestedRef.current = true;
          setIsLoadingHistory(true);
          wsClient.requestHistory();
        }
      },
      onDisconnect: () => {
        setIsConnected(false);
      },
      onCloseComplete: (deletedCount) => {
        console.log(`[useChatStream] Close complete: ${deletedCount} messages deleted`);
        onCloseCompleteRef.current?.(deletedCount);
      },
      onHistory: (messages) => {
        console.log(`[useChatStream] History loaded: ${messages.length} messages`);
        setIsLoadingHistory(false);
        onHistoryLoadedRef.current?.(messages);
      },
    });

    wsClient.connect();
    wsClientRef.current = wsClient;

    // Cleanup on unmount
    return () => {
      wsClient.disconnect();
      wsClientRef.current = null;
    };
  }, [conversationId]);

  // Send message
  const sendMessage = useCallback(
    (content: string, fileRefs?: ChatFileRef[], model?: string) => {
      if (!wsClientRef.current) {
        console.error("[useChatStream] WebSocket client not initialized");
        onError?.("Not connected");
        return;
      }

      // Get current settings from store
      const { temperature, thinkingEnabled } = useSettingsStore.getState();

      // Reset streaming state
      setStreamingContent("");
      setTokensUsed(null);
      setOutputTokens(null);
      setTotalTokensGenerated(null);
      setGenerationTime(null);
      setModelUsed(null);
      setIsStreaming(true);

      // Send message with selected model and settings
      wsClientRef.current.sendMessage(content, fileRefs, model, temperature, thinkingEnabled);
    },
    [onError]
  );

  // Reset streaming content (e.g., after adding to messages)
  const resetStream = useCallback(() => {
    setStreamingContent("");
    setTokensUsed(null);
    setOutputTokens(null);
    setTotalTokensGenerated(null);
    setGenerationTime(null);
    setModelUsed(null);
  }, []);

  // Close conversation and delete from backend
  const closeConversation = useCallback(() => {
    if (!wsClientRef.current) {
      console.error("[useChatStream] WebSocket client not initialized");
      onError?.("Not connected");
      return;
    }

    wsClientRef.current.closeConversation();
  }, [onError]);

  return {
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
    closeConversation,
  };
}
