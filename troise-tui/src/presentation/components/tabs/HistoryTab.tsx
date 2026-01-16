import React, { useState, useEffect } from "react";
import { Box, Text, useInput } from "ink";
import { useAppState, useDispatch, useServices } from "../../context/StateProvider";

interface SessionSummary {
  id: string;
  startTime: Date;
  messageCount: number;
  preview: string;
}

export function HistoryTab() {
  const state = useAppState();
  const dispatch = useDispatch();
  const { configStore } = useServices();
  const { colors } = state.ui.theme;

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  // Load session history
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    setLoading(true);
    try {
      // For now, use in-memory sessions
      // In a real implementation, this would load from persistent storage
      const mockSessions: SessionSummary[] = [
        {
          id: state.session.id || "current",
          startTime: state.session.startTime || new Date(),
          messageCount: state.chat.messages.length,
          preview: state.chat.messages[0]?.content.slice(0, 50) || "New session",
        },
      ];
      setSessions(mockSessions);
    } catch (error) {
      console.error("Failed to load sessions:", error);
    } finally {
      setLoading(false);
    }
  };

  // Handle keyboard input
  useInput((input, key) => {
    if (loading) return;

    if (key.upArrow) {
      setSelectedIndex((prev) => Math.max(0, prev - 1));
    } else if (key.downArrow) {
      setSelectedIndex((prev) => Math.min(sessions.length - 1, prev + 1));
    } else if (key.return) {
      // Load selected session
      const session = sessions[selectedIndex];
      if (session && session.id !== state.session.id) {
        // TODO: Implement session loading
        dispatch({
          type: "NOTIFICATION_ADDED",
          notification: {
            id: crypto.randomUUID(),
            type: "info",
            title: "Session Loading",
            message: "Session loading not yet implemented",
            autoDismiss: true,
            duration: 3000,
          },
        });
      }
    } else if (input === "n") {
      // New session
      dispatch({ type: "SESSION_CLEARED" });
      loadSessions();
    } else if (input === "d") {
      // Delete session
      // TODO: Implement session deletion
    } else if (input === "r") {
      // Refresh
      loadSessions();
    }
  });

  return (
    <Box flexDirection="column" flexGrow={1} padding={1}>
      {/* Header */}
      <Box marginBottom={1}>
        <Text color={colors.secondary} bold>
          📜 Session History
        </Text>
      </Box>

      {/* Session list */}
      <Box flexGrow={1} flexDirection="column" overflowY="hidden">
        {loading ? (
          <Text color={colors.textMuted}>Loading sessions...</Text>
        ) : sessions.length === 0 ? (
          <Box justifyContent="center" alignItems="center" flexGrow={1}>
            <Text color={colors.textMuted}>No previous sessions</Text>
          </Box>
        ) : (
          sessions.map((session, index) => (
            <SessionEntry
              key={session.id}
              session={session}
              isSelected={index === selectedIndex}
              isCurrent={session.id === state.session.id}
              colors={colors}
            />
          ))
        )}
      </Box>

      {/* Selected session details */}
      {sessions[selectedIndex] && (
        <Box
          flexDirection="column"
          borderStyle="single"
          borderColor={colors.border}
          padding={1}
          marginTop={1}
        >
          <Text color={colors.textMuted} bold>
            Session Details
          </Text>
          <Box marginTop={1} flexDirection="column">
            <Text color={colors.text}>
              ID: {sessions[selectedIndex].id}
            </Text>
            <Text color={colors.text}>
              Started: {sessions[selectedIndex].startTime.toLocaleString()}
            </Text>
            <Text color={colors.text}>
              Messages: {sessions[selectedIndex].messageCount}
            </Text>
          </Box>
        </Box>
      )}

      {/* Keyboard hints */}
      <Box marginTop={1} gap={2}>
        <Text color={colors.textMuted} dimColor>
          ↑/↓: Navigate
        </Text>
        <Text color={colors.textMuted} dimColor>
          Enter: Load session
        </Text>
        <Text color={colors.textMuted} dimColor>
          n: New session
        </Text>
        <Text color={colors.textMuted} dimColor>
          d: Delete
        </Text>
        <Text color={colors.textMuted} dimColor>
          r: Refresh
        </Text>
      </Box>
    </Box>
  );
}

interface SessionEntryProps {
  session: SessionSummary;
  isSelected: boolean;
  isCurrent: boolean;
  colors: Record<string, string>;
}

function SessionEntry({ session, isSelected, isCurrent, colors }: SessionEntryProps) {
  const timeStr = session.startTime.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <Box gap={1} marginBottom={1}>
      <Text color={isSelected ? colors.primary : colors.textMuted}>
        {isSelected ? "❯" : " "}
      </Text>
      {isCurrent && (
        <Text color={colors.success}>●</Text>
      )}
      <Text
        color={isSelected ? colors.primary : colors.text}
        bold={isSelected}
      >
        {session.preview.slice(0, 40)}
        {session.preview.length > 40 ? "..." : ""}
      </Text>
      <Text color={colors.textMuted} dimColor>
        ({session.messageCount} msgs)
      </Text>
      <Text color={colors.textMuted} dimColor>
        {timeStr}
      </Text>
    </Box>
  );
}
