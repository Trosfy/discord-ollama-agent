import React, { useState } from "react";
import { Box, Text, useInput } from "ink";
import { useAppState } from "../../context/StateProvider";

interface QuestionOption {
  label: string;
  value: string;
}

interface QuestionPromptProps {
  question: string;
  options?: QuestionOption[];
  onAnswer: (answer: string) => void;
}

export function QuestionPrompt({ question, options, onAnswer }: QuestionPromptProps) {
  const state = useAppState();
  const { colors } = state.ui.theme;
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [customInput, setCustomInput] = useState("");
  const [isCustomMode, setIsCustomMode] = useState(!options || options.length === 0);

  // Handle keyboard input
  useInput((input, key) => {
    if (isCustomMode) {
      // Custom text input mode
      if (key.return) {
        if (customInput.trim()) {
          onAnswer(customInput.trim());
        }
      } else if (key.escape) {
        if (options && options.length > 0) {
          setIsCustomMode(false);
          setCustomInput("");
        }
      } else if (key.backspace || key.delete) {
        setCustomInput((prev) => prev.slice(0, -1));
      } else if (input && !key.ctrl && !key.meta) {
        setCustomInput((prev) => prev + input);
      }
    } else {
      // Option selection mode
      if (key.upArrow) {
        setSelectedIndex((prev) => Math.max(0, prev - 1));
      } else if (key.downArrow) {
        setSelectedIndex((prev) => Math.min((options?.length || 1) - 1, prev + 1));
      } else if (key.return) {
        if (options && options[selectedIndex]) {
          onAnswer(options[selectedIndex].value);
        }
      } else if (input === "c" || input === "C") {
        setIsCustomMode(true);
      }
    }
  });

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={colors.accent}
      padding={1}
      marginY={1}
    >
      {/* Question */}
      <Box marginBottom={1}>
        <Text color={colors.accent} bold>
          ? {question}
        </Text>
      </Box>

      {/* Options */}
      {options && options.length > 0 && !isCustomMode && (
        <Box flexDirection="column">
          {options.map((option, index) => (
            <Box key={option.value} gap={1}>
              <Text color={index === selectedIndex ? colors.primary : colors.textMuted}>
                {index === selectedIndex ? "❯" : " "}
              </Text>
              <Text
                color={index === selectedIndex ? colors.primary : colors.text}
                bold={index === selectedIndex}
              >
                {option.label}
              </Text>
            </Box>
          ))}

          {/* Custom option hint */}
          <Box marginTop={1}>
            <Text color={colors.textMuted} dimColor>
              Press 'c' for custom response
            </Text>
          </Box>
        </Box>
      )}

      {/* Custom input */}
      {isCustomMode && (
        <Box flexDirection="column">
          <Box gap={1}>
            <Text color={colors.primary}>›</Text>
            <Text color={colors.text}>
              {customInput}
              <Text color={colors.accent}>▌</Text>
            </Text>
          </Box>

          {/* Hints */}
          <Box marginTop={1} gap={2}>
            <Text color={colors.textMuted} dimColor>
              Enter: Submit
            </Text>
            {options && options.length > 0 && (
              <Text color={colors.textMuted} dimColor>
                Esc: Back to options
              </Text>
            )}
          </Box>
        </Box>
      )}

      {/* Navigation hints */}
      {!isCustomMode && (
        <Box marginTop={1} gap={2}>
          <Text color={colors.textMuted} dimColor>
            ↑/↓: Navigate
          </Text>
          <Text color={colors.textMuted} dimColor>
            Enter: Select
          </Text>
        </Box>
      )}
    </Box>
  );
}
