import React from "react";
import { Box, Text } from "ink";
import { useAppState } from "../../context/StateProvider";

export function StatusBar() {
  const state = useAppState();
  const { colors } = state.ui.theme;

  const isConnected = state.connection.status === "connected";

  return (
    <Box paddingX={1}>
      <Text color={isConnected ? colors.success : colors.error}>
        {isConnected ? "●" : "○"}
      </Text>
      <Text dimColor> </Text>
      <Text dimColor>Esc=Exit</Text>
    </Box>
  );
}
