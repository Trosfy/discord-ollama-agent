import React, { useState, useEffect } from "react";
import { Box, Text } from "ink";
import { useAppState } from "../../context/StateProvider";

interface StreamingIndicatorProps {
  content: string;
}

export function StreamingIndicator({ content }: StreamingIndicatorProps) {
  const state = useAppState();
  const { colors } = state.ui.theme;
  const [dots, setDots] = useState("");

  // Animate dots while streaming
  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 300);

    return () => clearInterval(interval);
  }, []);

  return (
    <Box flexDirection="column" marginTop={1}>
      {/* Header */}
      <Box gap={1}>
        <Text color={colors.assistantMessage} bold>
          ◀ Troise
        </Text>
        <Text color={colors.accent}>
          thinking{dots}
        </Text>
      </Box>

      {/* Streaming content */}
      {content && (
        <Box paddingLeft={2}>
          <Text color={colors.text} wrap="wrap">
            {content}
          </Text>
          <Text color={colors.accent}>▌</Text>
        </Box>
      )}

      {/* Empty state with spinner */}
      {!content && (
        <Box paddingLeft={2}>
          <Spinner />
        </Box>
      )}
    </Box>
  );
}

// Simple spinner component
function Spinner() {
  const frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];
  const [frameIndex, setFrameIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setFrameIndex((prev) => (prev + 1) % frames.length);
    }, 80);

    return () => clearInterval(interval);
  }, []);

  return (
    <Text color="cyan">
      {frames[frameIndex]} Generating response...
    </Text>
  );
}
