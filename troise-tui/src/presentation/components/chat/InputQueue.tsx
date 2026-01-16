import React from "react";
import { Box, Text } from "ink";
import { useAppState } from "../../context/StateProvider";

interface InputQueueProps {
  items: string[];
}

export function InputQueue({ items }: InputQueueProps) {
  const state = useAppState();
  const { colors } = state.ui.theme;

  if (items.length === 0) {
    return null;
  }

  return (
    <Box
      flexDirection="column"
      borderStyle="single"
      borderColor={colors.border}
      padding={1}
      marginY={1}
    >
      {/* Header */}
      <Box marginBottom={1}>
        <Text color={colors.secondary} bold>
          📋 Queued Messages ({items.length})
        </Text>
      </Box>

      {/* Queue items */}
      <Box flexDirection="column">
        {items.map((item, index) => (
          <Box key={index} gap={1}>
            <Text color={colors.textMuted}>
              {index + 1}.
            </Text>
            <Text color={colors.text}>
              {item.length > 60 ? item.slice(0, 60) + "..." : item}
            </Text>
          </Box>
        ))}
      </Box>

      {/* Hint */}
      <Box marginTop={1}>
        <Text color={colors.textMuted} dimColor>
          Messages will be sent after current response completes
        </Text>
      </Box>
    </Box>
  );
}
