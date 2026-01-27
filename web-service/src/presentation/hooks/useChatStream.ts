/**
 * useChatStream Hook
 *
 * React hook for WebSocket chat streaming.
 * Manages connection, token streaming, and message state.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { ChatWebSocketClient, HistoryMessage, ChatFileRef, UserConfig } from "@/infrastructure/websocket/ChatWebSocket";
import { useSettingsStore } from "@/stores/settingsStore";
import { useAuthStore } from "@/stores/authStore";
import { FileHandlerAdapter } from "@/adapters/files/FileHandlerAdapter";
import type { IncomingFile, FileSuggestion, DecodedFile } from "@/core/types/file.types";

interface UseChatStreamOptions {
  conversationId: string;
  onSessionStart?: (sessionId: string) => void;
  onError?: (error: string) => void;
  onCloseComplete?: (deletedCount: number) => void;
  onHistoryLoaded?: (messages: HistoryMessage[]) => void;
  onFileReceived?: (file: DecodedFile) => void;
  onFileSuggestion?: (file: FileSuggestion) => void;
}

export function useChatStream({
  conversationId,
  onSessionStart,
  onError,
  onCloseComplete,
  onHistoryLoaded,
  onFileReceived,
  onFileSuggestion,
}: UseChatStreamOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [tokensUsed, setTokensUsed] = useState<number | null>(null);
  const [outputTokens, setOutputTokens] = useState<number | null>(null);
  const [totalTokensGenerated, setTotalTokensGenerated] = useState<number | null>(null);
  const [generationTime, setGenerationTime] = useState<number | null>(null);
  const [modelUsed, setModelUsed] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [receivedFiles, setReceivedFiles] = useState<DecodedFile[]>([]);
  const [pendingSuggestions, setPendingSuggestions] = useState<FileSuggestion[]>([]);

  const wsClientRef = useRef<ChatWebSocketClient | null>(null);
  const historyRequestedRef = useRef(false);
  const fileHandlerRef = useRef<FileHandlerAdapter>(new FileHandlerAdapter());

  // Store callbacks in refs to avoid reconnections
  const onSessionStartRef = useRef(onSessionStart);
  const onErrorRef = useRef(onError);
  const onCloseCompleteRef = useRef(onCloseComplete);
  const onHistoryLoadedRef = useRef(onHistoryLoaded);
  const onFileReceivedRef = useRef(onFileReceived);
  const onFileSuggestionRef = useRef(onFileSuggestion);

  useEffect(() => {
    onSessionStartRef.current = onSessionStart;
    onErrorRef.current = onError;
    onCloseCompleteRef.current = onCloseComplete;
    onHistoryLoadedRef.current = onHistoryLoaded;
    onFileReceivedRef.current = onFileReceived;
    onFileSuggestionRef.current = onFileSuggestion;
  }, [onSessionStart, onError, onCloseComplete, onHistoryLoaded, onFileReceived, onFileSuggestion]);

  // Initialize WebSocket connection
  useEffect(() => {
    historyRequestedRef.current = false;

    // Get user ID and auth token from auth store
    const authState = useAuthStore.getState();
    const userId = authState.user?.id || "anonymous";
    const authToken = authState.accessToken || undefined;

    const wsClient = new ChatWebSocketClient({
      sessionId: conversationId,
      userId,
      authToken, // Pass JWT token for authentication
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
        const tokenDisplay = totalTokens && totalTokens !== outTokens
          ? `${outTokens} tokens (${totalTokens} total)`
          : `${outTokens || tokens} tokens`;
        console.log(`[useChatStream] Stream complete: ${tokenDisplay} in ${genTime?.toFixed(2)}s, model: ${model}`);
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
      onSessionStart: (sessionId) => {
        console.log(`[useChatStream] Session started: ${sessionId}`);
        onSessionStartRef.current?.(sessionId);
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
      onFile: (file: IncomingFile) => {
        console.log(`[useChatStream] File received: ${file.filename} (source: ${file.source}, confidence: ${file.confidence})`);
        const decoded = fileHandlerRef.current.decode(file);
        setReceivedFiles((prev) => [...prev, decoded]);
        onFileReceivedRef.current?.(decoded);
      },
      onFileSuggestion: (suggestion: FileSuggestion) => {
        console.log(`[useChatStream] File suggestion: ${suggestion.filename} (source: ${suggestion.source}, confidence: ${suggestion.confidence})`);
        setPendingSuggestions((prev) => [...prev, suggestion]);
        onFileSuggestionRef.current?.(suggestion);
      },
    });

    wsClient.connect();
    wsClientRef.current = wsClient;

    // Cleanup on unmount
    return () => {
      wsClient.disconnect();
      wsClientRef.current = null;
      // Clean up Object URLs to prevent memory leaks
      fileHandlerRef.current.cleanup();
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

      // Build user config for TROISE-AI
      const userConfig: UserConfig | undefined = model || temperature !== undefined || thinkingEnabled !== undefined
        ? {
            model,
            temperature,
            thinking_enabled: thinkingEnabled,
          }
        : undefined;

      // Send message with user config
      wsClientRef.current.sendMessage(content, fileRefs, userConfig);
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

  // Accept a file suggestion (decode and add to received files)
  const acceptFileSuggestion = useCallback((suggestion: FileSuggestion) => {
    const decoded = fileHandlerRef.current.decode(suggestion);
    setReceivedFiles((prev) => [...prev, decoded]);
    setPendingSuggestions((prev) => prev.filter((s) => s.filename !== suggestion.filename));
    return decoded;
  }, []);

  // Dismiss a file suggestion
  const dismissFileSuggestion = useCallback((filename: string) => {
    setPendingSuggestions((prev) => prev.filter((s) => s.filename !== filename));
  }, []);

  // Clear all received files
  const clearFiles = useCallback(() => {
    fileHandlerRef.current.cleanup();
    setReceivedFiles([]);
    setPendingSuggestions([]);
  }, []);

  // Download a file
  const downloadFile = useCallback((file: DecodedFile) => {
    FileHandlerAdapter.downloadFile(file);
  }, []);

  return {
    // Connection state
    isConnected,
    isStreaming,
    isLoadingHistory,

    // Streaming content
    streamingContent,
    tokensUsed,
    outputTokens,
    totalTokensGenerated,
    generationTime,
    modelUsed,

    // File handling
    receivedFiles,
    pendingSuggestions,

    // Actions
    sendMessage,
    resetStream,
    closeConversation,
    acceptFileSuggestion,
    dismissFileSuggestion,
    clearFiles,
    downloadFile,
  };
}
