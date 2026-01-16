import React from "react";
import { Box, useInput, useApp } from "ink";
import { useAppState, useDispatch } from "../context/StateProvider";
import { ChatTab } from "./tabs/ChatTab";
import { SettingsTab } from "./tabs/SettingsTab";
import { StatusBar } from "./shared/StatusBar";
import { ConfirmDialog } from "./shared/ConfirmDialog";
import { CommandApprovalDialog } from "./shared/CommandApprovalDialog";
import { getTabByShortcut } from "@domain/value-objects";
import { actions } from "@application/state/actions";

export function App() {
  const state = useAppState();
  const dispatch = useDispatch();
  const { exit } = useApp();

  // Global keyboard shortcuts
  useInput((input, key) => {
    // Ctrl+C or Ctrl+Q to exit
    if (key.ctrl && (input === "c" || input === "q")) {
      exit();
      return;
    }

    // Escape to exit (backup)
    if (key.escape) {
      exit();
      return;
    }

    // Don't process shortcuts if modal is open
    if (state.ui.modals.confirmDialog || state.ui.modals.commandApproval) {
      return;
    }

    // Tab switching with number keys
    const tab = getTabByShortcut(input);
    if (tab) {
      dispatch(actions.tabChanged(tab));
      return;
    }

    // Ctrl+\ to toggle split view
    if (key.ctrl && input === "\\") {
      dispatch({ type: "SPLIT_VIEW_TOGGLED" });
      return;
    }

    // Ctrl+[ and Ctrl+] to adjust split ratio
    if (key.ctrl && input === "[") {
      dispatch({
        type: "SPLIT_VIEW_RATIO_CHANGED",
        ratio: state.ui.splitView.ratio - 10,
      });
      return;
    }
    if (key.ctrl && input === "]") {
      dispatch({
        type: "SPLIT_VIEW_RATIO_CHANGED",
        ratio: state.ui.splitView.ratio + 10,
      });
      return;
    }
  });

  // Render active tab content
  const renderTabContent = (tabType: string) => {
    switch (tabType) {
      case "chat":
        return <ChatTab />;
      case "settings":
        return <SettingsTab />;
      default:
        return <ChatTab />;
    }
  };

  // Get theme colors
  const { colors } = state.ui.theme;

  return (
    <Box flexDirection="column" width="100%" height="100%">
      {/* Main content area */}
      <Box flexGrow={1}>
        {renderTabContent(state.ui.activeTab)}
      </Box>

      {/* Status bar */}
      <StatusBar />

      {/* Modals */}
      {state.ui.modals.confirmDialog && (
        <ConfirmDialog {...state.ui.modals.confirmDialog} />
      )}
      {state.ui.modals.commandApproval && (
        <CommandApprovalDialog {...state.ui.modals.commandApproval} />
      )}
    </Box>
  );
}
