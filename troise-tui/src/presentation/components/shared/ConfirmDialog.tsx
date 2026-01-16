import React, { useState } from "react";
import { Box, Text, useInput } from "ink";
import { useAppState, useDispatch } from "../../context/StateProvider";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  danger?: boolean;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  danger = false,
}: ConfirmDialogProps) {
  const state = useAppState();
  const { colors } = state.ui.theme;
  const [selectedButton, setSelectedButton] = useState<"confirm" | "cancel">("cancel");

  useInput((input, key) => {
    if (key.leftArrow || key.rightArrow || key.tab) {
      setSelectedButton((prev) => (prev === "confirm" ? "cancel" : "confirm"));
    } else if (key.return) {
      if (selectedButton === "confirm") {
        onConfirm();
      } else {
        onCancel();
      }
    } else if (key.escape || input === "n" || input === "N") {
      onCancel();
    } else if (input === "y" || input === "Y") {
      onConfirm();
    }
  });

  const confirmColor = danger ? colors.error : colors.primary;

  return (
    <Box
      position="absolute"
      justifyContent="center"
      alignItems="center"
      width="100%"
      height="100%"
    >
      <Box
        flexDirection="column"
        borderStyle="double"
        borderColor={danger ? colors.error : colors.border}
        padding={2}
        minWidth={40}
      >
        {/* Title */}
        <Box marginBottom={1}>
          <Text color={danger ? colors.error : colors.primary} bold>
            {title}
          </Text>
        </Box>

        {/* Message */}
        <Box marginBottom={2}>
          <Text color={colors.text} wrap="wrap">
            {message}
          </Text>
        </Box>

        {/* Buttons */}
        <Box justifyContent="center" gap={4}>
          <Box
            borderStyle={selectedButton === "cancel" ? "round" : "single"}
            borderColor={selectedButton === "cancel" ? colors.primary : colors.border}
            paddingX={2}
          >
            <Text
              color={selectedButton === "cancel" ? colors.primary : colors.textMuted}
              bold={selectedButton === "cancel"}
            >
              {cancelLabel} (n)
            </Text>
          </Box>

          <Box
            borderStyle={selectedButton === "confirm" ? "round" : "single"}
            borderColor={selectedButton === "confirm" ? confirmColor : colors.border}
            paddingX={2}
          >
            <Text
              color={selectedButton === "confirm" ? confirmColor : colors.textMuted}
              bold={selectedButton === "confirm"}
            >
              {confirmLabel} (y)
            </Text>
          </Box>
        </Box>

        {/* Hints */}
        <Box marginTop={2} justifyContent="center">
          <Text color={colors.textMuted} dimColor>
            ←/→: Switch | Enter: Select | Esc: Cancel
          </Text>
        </Box>
      </Box>
    </Box>
  );
}
