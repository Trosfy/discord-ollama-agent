import React, { useState } from "react";
import { Box, Text, useInput } from "ink";
import { useAppState, useDispatch, useServices } from "../../context/StateProvider";

type SettingsSection = "profile" | "model" | "server" | "ui" | "execution";

interface SettingItem {
  key: string;
  label: string;
  value: string | number | boolean;
  type: "string" | "number" | "boolean" | "select";
  options?: string[];
}

export function SettingsTab() {
  const state = useAppState();
  const dispatch = useDispatch();
  const { configStore } = useServices();
  const { colors } = state.ui.theme;

  const [activeSection, setActiveSection] = useState<SettingsSection>("profile");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isEditing, setIsEditing] = useState(false);

  const sections: { key: SettingsSection; label: string; icon: string }[] = [
    { key: "profile", label: "Profile", icon: "👤" },
    { key: "model", label: "Model", icon: "🤖" },
    { key: "server", label: "Server", icon: "🌐" },
    { key: "ui", label: "UI", icon: "🎨" },
    { key: "execution", label: "Execution", icon: "⚡" },
  ];

  // Get settings for current section
  const getSettings = (): SettingItem[] => {
    const profile = state.config.activeProfile;

    switch (activeSection) {
      case "profile":
        return [
          { key: "name", label: "Profile Name", value: profile?.name || "default", type: "string" },
          { key: "systemPrompt", label: "System Prompt", value: profile?.systemPrompt || "(default)", type: "string" },
        ];
      case "model":
        return [
          { key: "name", label: "Model", value: profile?.model?.name || "default", type: "string" },
          { key: "temperature", label: "Temperature", value: profile?.model?.temperature || 0.7, type: "number" },
          { key: "maxTokens", label: "Max Tokens", value: profile?.model?.maxTokens || 4096, type: "number" },
          { key: "showThinking", label: "Show Thinking", value: profile?.model?.showThinking ?? true, type: "boolean" },
          { key: "contextLength", label: "Context Length", value: profile?.model?.contextLength || 8192, type: "number" },
        ];
      case "server":
        return [
          { key: "url", label: "Server URL", value: state.connection.serverUrl, type: "string" },
          { key: "reconnectDelay", label: "Reconnect Delay", value: 3000, type: "number" },
        ];
      case "ui":
        return [
          { key: "theme", label: "Theme", value: state.ui.theme.name, type: "select", options: ["auto", "dark", "light"] },
          { key: "splitView", label: "Split View", value: state.ui.splitView.enabled, type: "boolean" },
          { key: "splitRatio", label: "Split Ratio", value: state.ui.splitView.ratio, type: "number" },
        ];
      case "execution":
        return [
          { key: "shell", label: "Shell", value: profile?.execution?.shell || "/bin/bash", type: "string" },
          { key: "workingDir", label: "Working Dir", value: state.shell.workingDir, type: "string" },
          { key: "commandTimeout", label: "Command Timeout", value: profile?.execution?.commandTimeout || 30000, type: "number" },
          { key: "autoApprove", label: "Auto-approve Safe", value: profile?.execution?.autoApproveSafe ?? false, type: "boolean" },
        ];
      default:
        return [];
    }
  };

  const settings = getSettings();

  // Handle keyboard input
  useInput((input, key) => {
    if (isEditing) {
      // TODO: Handle editing mode
      if (key.escape) {
        setIsEditing(false);
      }
      return;
    }

    // Section navigation
    if (key.leftArrow) {
      const currentIndex = sections.findIndex((s) => s.key === activeSection);
      if (currentIndex > 0) {
        setActiveSection(sections[currentIndex - 1].key);
        setSelectedIndex(0);
      }
    } else if (key.rightArrow) {
      const currentIndex = sections.findIndex((s) => s.key === activeSection);
      if (currentIndex < sections.length - 1) {
        setActiveSection(sections[currentIndex + 1].key);
        setSelectedIndex(0);
      }
    } else if (key.upArrow) {
      setSelectedIndex((prev) => Math.max(0, prev - 1));
    } else if (key.downArrow) {
      setSelectedIndex((prev) => Math.min(settings.length - 1, prev + 1));
    } else if (key.return) {
      const setting = settings[selectedIndex];
      if (setting.type === "boolean") {
        // Toggle boolean
        handleSettingChange(setting.key, !setting.value);
      } else {
        setIsEditing(true);
      }
    } else if (input === "r") {
      // Reset to defaults
      dispatch({
        type: "NOTIFICATION_ADDED",
        notification: {
          id: crypto.randomUUID(),
          type: "info",
          title: "Reset",
          message: "Settings reset not yet implemented",
          autoDismiss: true,
          duration: 3000,
        },
      });
    }
  });

  const handleSettingChange = (key: string, value: string | number | boolean) => {
    // TODO: Implement setting changes
    dispatch({
      type: "NOTIFICATION_ADDED",
      notification: {
        id: crypto.randomUUID(),
        type: "info",
        title: "Setting Changed",
        message: `${key} = ${value}`,
        autoDismiss: true,
        duration: 2000,
      },
    });
  };

  return (
    <Box flexDirection="column" flexGrow={1} padding={1}>
      {/* Section tabs */}
      <Box marginBottom={1} gap={2}>
        {sections.map((section) => (
          <Box key={section.key} gap={1}>
            <Text
              color={section.key === activeSection ? colors.primary : colors.textMuted}
              bold={section.key === activeSection}
              underline={section.key === activeSection}
            >
              {section.icon} {section.label}
            </Text>
          </Box>
        ))}
      </Box>

      {/* Settings list */}
      <Box flexGrow={1} flexDirection="column">
        {settings.map((setting, index) => (
          <SettingRow
            key={setting.key}
            setting={setting}
            isSelected={index === selectedIndex}
            colors={colors}
          />
        ))}
      </Box>

      {/* Keyboard hints */}
      <Box marginTop={1} gap={2}>
        <Text color={colors.textMuted} dimColor>
          ←/→: Section
        </Text>
        <Text color={colors.textMuted} dimColor>
          ↑/↓: Navigate
        </Text>
        <Text color={colors.textMuted} dimColor>
          Enter: Edit/Toggle
        </Text>
        <Text color={colors.textMuted} dimColor>
          r: Reset
        </Text>
      </Box>
    </Box>
  );
}

interface SettingRowProps {
  setting: SettingItem;
  isSelected: boolean;
  colors: Record<string, string>;
}

function SettingRow({ setting, isSelected, colors }: SettingRowProps) {
  const formatValue = () => {
    if (typeof setting.value === "boolean") {
      return setting.value ? "✓ On" : "✗ Off";
    }
    if (typeof setting.value === "string" && setting.value.length > 30) {
      return setting.value.slice(0, 30) + "...";
    }
    return String(setting.value);
  };

  const valueColor =
    typeof setting.value === "boolean"
      ? setting.value
        ? colors.success
        : colors.error
      : colors.accent;

  return (
    <Box gap={2} marginBottom={1}>
      <Text color={isSelected ? colors.primary : colors.textMuted}>
        {isSelected ? "❯" : " "}
      </Text>
      <Box width={20}>
        <Text
          color={isSelected ? colors.primary : colors.text}
          bold={isSelected}
        >
          {setting.label}
        </Text>
      </Box>
      <Text color={valueColor}>{formatValue()}</Text>
    </Box>
  );
}
