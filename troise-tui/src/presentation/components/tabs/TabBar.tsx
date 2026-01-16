import React from "react";
import { Box, Text } from "ink";
import { useAppState } from "../../context/StateProvider";
import {
  TAB_ORDER,
  TAB_LABELS,
  TAB_SHORTCUTS,
  TAB_ICONS,
  type TabType,
} from "@domain/value-objects";

interface TabBarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

export function TabBar({ activeTab, onTabChange }: TabBarProps) {
  const state = useAppState();
  const { colors } = state.ui.theme;

  return (
    <Box paddingX={1} gap={2}>
      {TAB_ORDER.map((tab) => {
        const isActive = tab === activeTab;
        const icon = TAB_ICONS[tab];
        const label = TAB_LABELS[tab];
        const shortcut = TAB_SHORTCUTS[tab];

        return (
          <Box key={tab} gap={1}>
            <Text
              color={isActive ? colors.primary : colors.textMuted}
              bold={isActive}
              underline={isActive}
            >
              {icon} {label}
            </Text>
            <Text color={colors.textMuted} dimColor>
              [{shortcut}]
            </Text>
          </Box>
        );
      })}

      {/* Split view indicator */}
      {state.ui.splitView.enabled && (
        <Box marginLeft={2}>
          <Text color={colors.accent}>⊞ Split</Text>
        </Box>
      )}
    </Box>
  );
}
