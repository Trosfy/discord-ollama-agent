import React, { useState, useEffect } from "react";
import { Box, Text, useInput } from "ink";
import { useAppState, useDispatch, useServices } from "../../context/StateProvider";
import { actions } from "@application/state/actions";

export function FilesTab() {
  const state = useAppState();
  const dispatch = useDispatch();
  const { fileSystem } = useServices();
  const { colors } = state.ui.theme;

  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [previewContent, setPreviewContent] = useState<string | null>(null);

  const entries = state.files.entries;
  const currentPath = state.files.currentPath;

  // Load directory on mount or path change
  useEffect(() => {
    loadDirectory(currentPath);
  }, [currentPath]);

  const loadDirectory = async (path: string) => {
    setLoading(true);
    try {
      const dirEntries = await fileSystem.readDirectory(path);
      dispatch(actions.filesLoaded(path, dirEntries));
      setSelectedIndex(0);
    } catch (error) {
      dispatch({
        type: "NOTIFICATION_ADDED",
        notification: {
          id: crypto.randomUUID(),
          type: "error",
          title: "Error",
          message: `Failed to load directory: ${error}`,
          autoDismiss: true,
          duration: 5000,
        },
      });
    } finally {
      setLoading(false);
    }
  };

  // Load file preview
  const loadPreview = async (entry: { name: string; isDirectory: boolean }) => {
    if (entry.isDirectory) {
      setPreviewContent(null);
      return;
    }

    try {
      const fullPath = `${currentPath}/${entry.name}`;
      const content = await fileSystem.readFile(fullPath, { maxLines: 20 });
      setPreviewContent(content);
    } catch {
      setPreviewContent("[Unable to preview file]");
    }
  };

  // Handle keyboard input
  useInput(async (input, key) => {
    if (loading) return;

    if (key.upArrow) {
      const newIndex = Math.max(0, selectedIndex - 1);
      setSelectedIndex(newIndex);
      if (entries[newIndex]) {
        loadPreview(entries[newIndex]);
      }
    } else if (key.downArrow) {
      const newIndex = Math.min(entries.length - 1, selectedIndex + 1);
      setSelectedIndex(newIndex);
      if (entries[newIndex]) {
        loadPreview(entries[newIndex]);
      }
    } else if (key.return) {
      const entry = entries[selectedIndex];
      if (entry?.isDirectory) {
        const newPath = entry.name === ".."
          ? currentPath.split("/").slice(0, -1).join("/") || "/"
          : `${currentPath}/${entry.name}`;
        dispatch(actions.pathChanged(newPath));
      }
    } else if (key.backspace || input === "h") {
      // Go up one directory
      const parentPath = currentPath.split("/").slice(0, -1).join("/") || "/";
      dispatch(actions.pathChanged(parentPath));
    } else if (input === "r") {
      // Refresh
      loadDirectory(currentPath);
    } else if (input === "a") {
      // Attach selected file
      const entry = entries[selectedIndex];
      if (entry && !entry.isDirectory) {
        dispatch(actions.fileSelected(`${currentPath}/${entry.name}`));
      }
    }
  });

  // Initial preview load
  useEffect(() => {
    if (entries[selectedIndex]) {
      loadPreview(entries[selectedIndex]);
    }
  }, [selectedIndex, entries]);

  return (
    <Box flexDirection="column" flexGrow={1} padding={1}>
      {/* Path breadcrumb */}
      <Box marginBottom={1}>
        <Text color={colors.secondary} bold>
          📁 {currentPath}
        </Text>
      </Box>

      {/* Main content */}
      <Box flexGrow={1} flexDirection="row">
        {/* File list */}
        <Box flexDirection="column" flexBasis="50%" overflowY="hidden">
          {loading ? (
            <Text color={colors.textMuted}>Loading...</Text>
          ) : entries.length === 0 ? (
            <Text color={colors.textMuted}>Empty directory</Text>
          ) : (
            entries.map((entry, index) => (
              <FileEntry
                key={entry.name}
                entry={entry}
                isSelected={index === selectedIndex}
                colors={colors}
              />
            ))
          )}
        </Box>

        {/* Preview panel */}
        <Box
          flexDirection="column"
          flexBasis="50%"
          borderStyle="single"
          borderColor={colors.border}
          padding={1}
          marginLeft={1}
        >
          <Text color={colors.textMuted} bold>
            Preview
          </Text>
          <Box marginTop={1}>
            {previewContent ? (
              <Text color={colors.text} wrap="truncate-end">
                {previewContent}
              </Text>
            ) : (
              <Text color={colors.textMuted} dimColor>
                {entries[selectedIndex]?.isDirectory
                  ? "Select a file to preview"
                  : "No preview available"}
              </Text>
            )}
          </Box>
        </Box>
      </Box>

      {/* Keyboard hints */}
      <Box marginTop={1} gap={2}>
        <Text color={colors.textMuted} dimColor>
          ↑/↓: Navigate
        </Text>
        <Text color={colors.textMuted} dimColor>
          Enter: Open folder
        </Text>
        <Text color={colors.textMuted} dimColor>
          h/←: Parent
        </Text>
        <Text color={colors.textMuted} dimColor>
          a: Attach file
        </Text>
        <Text color={colors.textMuted} dimColor>
          r: Refresh
        </Text>
      </Box>
    </Box>
  );
}

interface FileEntryProps {
  entry: {
    name: string;
    isDirectory: boolean;
    size?: number;
    modified?: Date;
  };
  isSelected: boolean;
  colors: Record<string, string>;
}

function FileEntry({ entry, isSelected, colors }: FileEntryProps) {
  const icon = entry.isDirectory ? "📁" : getFileIcon(entry.name);
  const sizeStr = entry.size ? formatSize(entry.size) : "";

  return (
    <Box gap={1}>
      <Text color={isSelected ? colors.primary : colors.textMuted}>
        {isSelected ? "❯" : " "}
      </Text>
      <Text>{icon}</Text>
      <Text
        color={isSelected ? colors.primary : entry.isDirectory ? colors.secondary : colors.text}
        bold={isSelected}
      >
        {entry.name}
      </Text>
      {sizeStr && (
        <Text color={colors.textMuted} dimColor>
          {sizeStr}
        </Text>
      )}
    </Box>
  );
}

function getFileIcon(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  const icons: Record<string, string> = {
    ts: "📘",
    tsx: "📘",
    js: "📒",
    jsx: "📒",
    json: "📋",
    md: "📝",
    py: "🐍",
    rs: "🦀",
    go: "🐹",
    sh: "💻",
    yml: "⚙️",
    yaml: "⚙️",
    toml: "⚙️",
    env: "🔒",
    git: "🌿",
    lock: "🔐",
  };
  return icons[ext || ""] || "📄";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}K`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)}M`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)}G`;
}
