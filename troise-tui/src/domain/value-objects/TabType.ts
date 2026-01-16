/**
 * TabType - available tabs in the TUI
 */
export type TabType = "chat" | "settings";

export const TAB_ORDER: TabType[] = ["chat", "settings"];

export const TAB_LABELS: Record<TabType, string> = {
  chat: "Chat",
  settings: "Settings",
};

export const TAB_SHORTCUTS: Record<TabType, string> = {
  chat: "1",
  settings: "2",
};

export const TAB_ICONS: Record<TabType, string> = {
  chat: ">",
  settings: "*",
};

/**
 * Get tab by shortcut key
 */
export function getTabByShortcut(key: string): TabType | undefined {
  const entries = Object.entries(TAB_SHORTCUTS);
  const found = entries.find(([, shortcut]) => shortcut === key);
  return found ? (found[0] as TabType) : undefined;
}

/**
 * Get next tab in order
 */
export function getNextTab(current: TabType): TabType {
  const index = TAB_ORDER.indexOf(current);
  return TAB_ORDER[(index + 1) % TAB_ORDER.length];
}

/**
 * Get previous tab in order
 */
export function getPreviousTab(current: TabType): TabType {
  const index = TAB_ORDER.indexOf(current);
  return TAB_ORDER[(index - 1 + TAB_ORDER.length) % TAB_ORDER.length];
}
