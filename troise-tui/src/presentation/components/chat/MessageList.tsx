import React, { useState, useEffect } from "react";
import { Box, Text, useInput, useStdout } from "ink";
import type { Message } from "@domain/entities";
import { useAppState } from "../../context/StateProvider";

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  const state = useAppState();
  const { colors } = state.ui.theme;
  const { stdout } = useStdout();
  const [scrollOffset, setScrollOffset] = useState(0);

  // Calculate visible area (leave room for input and status bar)
  const terminalHeight = stdout?.rows || 24;
  const visibleLines = Math.max(10, terminalHeight - 8);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    setScrollOffset(0);
  }, [messages.length]);

  // Handle scroll with arrow keys
  useInput((input, key) => {
    if (key.upArrow || (key.ctrl && input === "p")) {
      setScrollOffset((prev) => Math.min(prev + 3, messages.length - 1));
    }
    if (key.downArrow || (key.ctrl && input === "n")) {
      setScrollOffset((prev) => Math.max(prev - 3, 0));
    }
    // Page up/down
    if (key.pageUp) {
      setScrollOffset((prev) => Math.min(prev + 10, messages.length - 1));
    }
    if (key.pageDown) {
      setScrollOffset((prev) => Math.max(prev - 10, 0));
    }
  });

  if (messages.length === 0) {
    return (
      <Box flexDirection="column" paddingX={1}>
        <Text dimColor>No messages yet</Text>
      </Box>
    );
  }

  // Show messages from the end, with scroll offset
  const endIndex = messages.length - scrollOffset;
  const startIndex = Math.max(0, endIndex - 20); // Show last 20 messages max
  const visibleMessages = messages.slice(startIndex, endIndex);

  return (
    <Box flexDirection="column" gap={1}>
      {scrollOffset > 0 && (
        <Text dimColor>↑ {scrollOffset} more above (use arrow keys to scroll)</Text>
      )}
      {visibleMessages.map((message) => (
        <MessageItem key={message.id} message={message} colors={colors} />
      ))}
    </Box>
  );
}

interface MessageItemProps {
  message: Message;
  colors: Record<string, string>;
}

function MessageItem({ message, colors }: MessageItemProps) {
  const isUser = message.role === "user";

  if (isUser) {
    // User messages: left-aligned with background highlight
    return (
      <Box marginBottom={1}>
        <Text backgroundColor="gray" color="white" bold>
          {" "}{message.content}{" "}
        </Text>
      </Box>
    );
  }

  // Assistant messages
  return (
    <Box flexDirection="column" marginBottom={1}>
      <Text color={colors.text} wrap="wrap">
        {message.content}
      </Text>

      {/* Tool calls */}
      {message.metadata?.toolCalls && message.metadata.toolCalls.length > 0 && (
        <Box paddingLeft={2} flexDirection="column" marginTop={1}>
          {message.metadata.toolCalls.map((tool, index) => (
            <Box key={index} gap={1}>
              <Text color={colors.accent}>⚡</Text>
              <Text color={colors.textMuted}>
                {tool.name}
                {tool.result ? " ✓" : " ..."}
              </Text>
            </Box>
          ))}
        </Box>
      )}

      {/* Attachments */}
      {message.metadata?.attachments && message.metadata.attachments.length > 0 && (
        <Box paddingLeft={2} flexDirection="column" marginTop={1}>
          {message.metadata.attachments.map((attachment, index) => (
            <Box key={index} gap={1}>
              <Text color={colors.secondary}>📎</Text>
              <Text color={colors.textMuted}>{attachment.filename}</Text>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
