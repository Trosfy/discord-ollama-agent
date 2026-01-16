import React, { useState } from "react";
import { Box, Text, useInput } from "ink";
import { useAppState } from "../../context/StateProvider";
import { isDangerousCommand } from "@domain/entities";

interface CommandApprovalDialogProps {
  command: string;
  requestId: string;
  onApprove: () => void;
  onReject: () => void;
}

export function CommandApprovalDialog({
  command,
  requestId,
  onApprove,
  onReject,
}: CommandApprovalDialogProps) {
  const state = useAppState();
  const { colors } = state.ui.theme;
  const [selectedButton, setSelectedButton] = useState<"approve" | "reject">("reject");

  const isDangerous = isDangerousCommand(command);

  useInput((input, key) => {
    if (key.leftArrow || key.rightArrow || key.tab) {
      setSelectedButton((prev) => (prev === "approve" ? "reject" : "approve"));
    } else if (key.return) {
      if (selectedButton === "approve") {
        onApprove();
      } else {
        onReject();
      }
    } else if (key.escape || input === "n" || input === "N") {
      onReject();
    } else if (input === "y" || input === "Y") {
      onApprove();
    }
  });

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
        borderColor={isDangerous ? colors.error : colors.warning}
        padding={2}
        minWidth={50}
      >
        {/* Header */}
        <Box marginBottom={1} gap={1}>
          <Text color={isDangerous ? colors.error : colors.warning} bold>
            {isDangerous ? "⚠ DANGEROUS COMMAND" : "🔧 Command Approval Required"}
          </Text>
        </Box>

        {/* Explanation */}
        <Box marginBottom={1}>
          <Text color={colors.textMuted}>
            The AI agent wants to execute the following command:
          </Text>
        </Box>

        {/* Command */}
        <Box
          borderStyle="single"
          borderColor={colors.border}
          padding={1}
          marginBottom={1}
        >
          <Text color={colors.code} wrap="wrap">
            $ {command}
          </Text>
        </Box>

        {/* Danger warning */}
        {isDangerous && (
          <Box marginBottom={1}>
            <Text color={colors.error}>
              ⚠ This command has been flagged as potentially dangerous.
              Review carefully before approving.
            </Text>
          </Box>
        )}

        {/* Request ID */}
        <Box marginBottom={2}>
          <Text color={colors.textMuted} dimColor>
            Request ID: {requestId.slice(0, 12)}...
          </Text>
        </Box>

        {/* Buttons */}
        <Box justifyContent="center" gap={4}>
          <Box
            borderStyle={selectedButton === "reject" ? "round" : "single"}
            borderColor={selectedButton === "reject" ? colors.error : colors.border}
            paddingX={2}
          >
            <Text
              color={selectedButton === "reject" ? colors.error : colors.textMuted}
              bold={selectedButton === "reject"}
            >
              Reject (n)
            </Text>
          </Box>

          <Box
            borderStyle={selectedButton === "approve" ? "round" : "single"}
            borderColor={selectedButton === "approve" ? colors.success : colors.border}
            paddingX={2}
          >
            <Text
              color={selectedButton === "approve" ? colors.success : colors.textMuted}
              bold={selectedButton === "approve"}
            >
              Approve (y)
            </Text>
          </Box>
        </Box>

        {/* Hints */}
        <Box marginTop={2} justifyContent="center">
          <Text color={colors.textMuted} dimColor>
            ←/→: Switch | Enter: Select | Esc: Reject
          </Text>
        </Box>
      </Box>
    </Box>
  );
}
