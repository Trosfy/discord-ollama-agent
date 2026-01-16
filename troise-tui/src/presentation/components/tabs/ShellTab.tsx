import React, { useState, useRef, useEffect } from "react";
import { Box, Text, useInput } from "ink";
import TextInput from "ink-text-input";
import { useAppState, useDispatch, useServices } from "../../context/StateProvider";
import { actions } from "@application/state/actions";
import { isDangerousCommand } from "@domain/entities";

export function ShellTab() {
  const state = useAppState();
  const dispatch = useDispatch();
  const { commandExecutor } = useServices();
  const { colors } = state.ui.theme;

  const [input, setInput] = useState("");
  const [isExecuting, setIsExecuting] = useState(false);

  const history = state.shell.history;
  const workingDir = state.shell.workingDir;

  // Handle command submission
  const handleSubmit = async (value: string) => {
    if (!value.trim() || isExecuting) return;

    const command = value.trim();
    setInput("");

    // Add to history
    dispatch(actions.commandExecuted(command));

    // Check for dangerous commands
    if (isDangerousCommand(command)) {
      dispatch({
        type: "CONFIRM_DIALOG_OPENED",
        dialog: {
          title: "Dangerous Command",
          message: `This command has been flagged as potentially dangerous:\n\n${command}\n\nAre you sure you want to execute it?`,
          danger: true,
          onConfirm: async () => {
            dispatch({ type: "CONFIRM_DIALOG_CLOSED" });
            await executeCommand(command);
          },
          onCancel: () => {
            dispatch({ type: "CONFIRM_DIALOG_CLOSED" });
            dispatch(actions.commandOutputReceived(
              history.length,
              "",
              "Command cancelled by user",
              1
            ));
          },
        },
      });
      return;
    }

    await executeCommand(command);
  };

  const executeCommand = async (command: string) => {
    setIsExecuting(true);

    // Handle cd specially
    if (command.startsWith("cd ")) {
      const newDir = command.slice(3).trim();
      const resolvedPath = newDir.startsWith("/")
        ? newDir
        : `${workingDir}/${newDir}`;

      try {
        // Verify directory exists
        await commandExecutor.execute(`test -d "${resolvedPath}"`);
        dispatch(actions.workingDirChanged(resolvedPath));
        dispatch(actions.commandOutputReceived(
          history.length,
          `Changed directory to ${resolvedPath}`,
          "",
          0
        ));
      } catch {
        dispatch(actions.commandOutputReceived(
          history.length,
          "",
          `cd: no such directory: ${newDir}`,
          1
        ));
      }
      setIsExecuting(false);
      return;
    }

    try {
      const result = await commandExecutor.execute(command, { cwd: workingDir });
      dispatch(actions.commandOutputReceived(
        history.length,
        result.stdout,
        result.stderr,
        result.exitCode
      ));
    } catch (error) {
      dispatch(actions.commandOutputReceived(
        history.length,
        "",
        String(error),
        1
      ));
    } finally {
      setIsExecuting(false);
    }
  };

  // Keyboard shortcuts
  useInput((inputKey, key) => {
    if (key.ctrl && inputKey === "c" && isExecuting) {
      // TODO: Cancel running command
    } else if (key.ctrl && inputKey === "l") {
      dispatch({ type: "SHELL_HISTORY_CLEARED" });
    }
  });

  return (
    <Box flexDirection="column" flexGrow={1} padding={1}>
      {/* Working directory */}
      <Box marginBottom={1}>
        <Text color={colors.secondary} bold>
          💻 {workingDir}
        </Text>
      </Box>

      {/* History */}
      <Box flexGrow={1} flexDirection="column" overflowY="hidden">
        {history.length === 0 ? (
          <Box justifyContent="center" alignItems="center" flexGrow={1}>
            <Text color={colors.textMuted}>
              No commands yet. Type a command below.
            </Text>
          </Box>
        ) : (
          history.map((entry, index) => (
            <HistoryEntry
              key={index}
              entry={entry}
              colors={colors}
              isLast={index === history.length - 1}
            />
          ))
        )}
      </Box>

      {/* Input */}
      <Box
        borderStyle="round"
        borderColor={isExecuting ? colors.warning : colors.border}
        marginTop={1}
      >
        <Box paddingX={1}>
          <Text color={colors.accent}>$</Text>
          <Text> </Text>
          <TextInput
            value={input}
            onChange={setInput}
            onSubmit={handleSubmit}
            placeholder={isExecuting ? "Running..." : "Enter command..."}
          />
        </Box>
      </Box>

      {/* Keyboard hints */}
      <Box marginTop={1} gap={2}>
        <Text color={colors.textMuted} dimColor>
          Enter: Execute
        </Text>
        <Text color={colors.textMuted} dimColor>
          Ctrl+L: Clear
        </Text>
        {isExecuting && (
          <Text color={colors.textMuted} dimColor>
            Ctrl+C: Cancel
          </Text>
        )}
      </Box>
    </Box>
  );
}

interface HistoryEntryProps {
  entry: {
    command: string;
    stdout?: string;
    stderr?: string;
    exitCode?: number;
    timestamp: Date;
  };
  colors: Record<string, string>;
  isLast: boolean;
}

function HistoryEntry({ entry, colors, isLast }: HistoryEntryProps) {
  const time = entry.timestamp.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const exitColor =
    entry.exitCode === undefined
      ? colors.textMuted
      : entry.exitCode === 0
      ? colors.success
      : colors.error;

  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* Command line */}
      <Box gap={1}>
        <Text color={colors.textMuted} dimColor>
          {time}
        </Text>
        <Text color={colors.accent}>$</Text>
        <Text color={colors.code}>{entry.command}</Text>
        {entry.exitCode !== undefined && (
          <Text color={exitColor}>
            [{entry.exitCode}]
          </Text>
        )}
      </Box>

      {/* Output */}
      {entry.stdout && (
        <Box paddingLeft={2}>
          <Text color={colors.text} wrap="truncate-end">
            {entry.stdout.slice(0, 500)}
            {entry.stdout.length > 500 && "..."}
          </Text>
        </Box>
      )}

      {/* Error output */}
      {entry.stderr && (
        <Box paddingLeft={2}>
          <Text color={colors.error} wrap="truncate-end">
            {entry.stderr.slice(0, 500)}
            {entry.stderr.length > 500 && "..."}
          </Text>
        </Box>
      )}
    </Box>
  );
}
