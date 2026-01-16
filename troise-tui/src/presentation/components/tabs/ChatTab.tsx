import React, { useState, useEffect, useRef } from "react";
import { Box, Text, useInput } from "ink";
import TextInput from "ink-text-input";
import { useAppState, useDispatch, useServices } from "../../context/StateProvider";
import { MessageList } from "../chat/MessageList";
import { StreamingIndicator } from "../chat/StreamingIndicator";
import { QuestionPrompt } from "../chat/QuestionPrompt";
import { InputQueue } from "../chat/InputQueue";
import { createUserMessage } from "@domain/entities";
import { actions } from "@application/state/actions";

export function ChatTab() {
  const state = useAppState();
  const dispatch = useDispatch();
  const { wsClient } = useServices();
  const [input, setInput] = useState("");
  const { colors } = state.ui.theme;

  // Auto-dismiss errors after 5 seconds
  useEffect(() => {
    if (state.chat.error) {
      const timer = setTimeout(() => {
        dispatch({ type: "CHAT_ERROR_CLEARED" });
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [state.chat.error, dispatch]);

  // Handle input submission
  const handleSubmit = async (value: string) => {
    if (!value.trim()) return;

    // If we're streaming, queue the input
    if (state.chat.isStreaming) {
      dispatch(actions.inputQueued(value));
      setInput("");
      return;
    }

    // Add user message to state
    const message = createUserMessage(value);
    dispatch(actions.messageAdded(message));

    // Clear input
    setInput("");

    // Send to server
    try {
      await wsClient.sendMessage(value);
    } catch (error) {
      dispatch({ type: "CHAT_ERROR", error: String(error) });
    }
  };

  // Handle question answer
  const handleAnswer = async (answer: string) => {
    if (!state.chat.pendingQuestion) return;

    try {
      await wsClient.sendAnswer(state.chat.pendingQuestion.requestId, answer);
      dispatch({ type: "QUESTION_ANSWERED" });
    } catch (error) {
      dispatch({ type: "CHAT_ERROR", error: String(error) });
    }
  };

  // Keyboard shortcuts
  useInput((inputKey, key) => {
    // Ctrl+C to cancel streaming
    if (key.ctrl && inputKey === "c" && state.chat.isStreaming) {
      if (state.chat.streamingRequestId) {
        wsClient.cancelRequest(state.chat.streamingRequestId);
      }
    }
  });

  const isConnected = state.connection.status === "connected";
  const canSend = isConnected && !state.chat.pendingQuestion;

  return (
    <Box flexDirection="column" flexGrow={1}>
      {/* Message list - takes all available space */}
      <Box flexGrow={1} flexDirection="column" overflowY="hidden" paddingX={1} paddingTop={1}>
        <MessageList messages={state.chat.messages} />

        {/* Streaming content */}
        {state.chat.isStreaming && (
          <StreamingIndicator content={state.chat.streamingContent} />
        )}
      </Box>

      {/* Input queue (shown when streaming) */}
      {state.chat.inputQueue.length > 0 && (
        <Box paddingX={1}>
          <InputQueue items={state.chat.inputQueue} />
        </Box>
      )}

      {/* Question prompt (shown when agent asks a question) */}
      {state.chat.pendingQuestion && (
        <Box paddingX={1}>
          <QuestionPrompt
            question={state.chat.pendingQuestion.question}
            options={state.chat.pendingQuestion.options}
            onAnswer={handleAnswer}
          />
        </Box>
      )}

      {/* Error display */}
      {state.chat.error && (
        <Box paddingX={1} marginBottom={1}>
          <Text color={colors.error}>✗ {state.chat.error}</Text>
        </Box>
      )}

      {/* Input area */}
      {!state.chat.pendingQuestion && (
        <Box flexDirection="column" paddingX={1} paddingBottom={1}>
          {/* Input box */}
          <Box
            borderStyle="round"
            borderColor={isConnected ? colors.borderFocus : colors.error}
          >
            <Box paddingX={1}>
              <Text color={isConnected ? colors.primary : colors.error} bold>
                {state.chat.isStreaming ? "+" : ">"}
              </Text>
              <Text> </Text>
              <TextInput
                value={input}
                onChange={setInput}
                onSubmit={handleSubmit}
                placeholder={
                  !isConnected
                    ? "Waiting for connection..."
                    : state.chat.isStreaming
                    ? "Queue another message..."
                    : "Ask me anything..."
                }
              />
            </Box>
          </Box>

        </Box>
      )}
    </Box>
  );
}
