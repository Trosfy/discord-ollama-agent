"use client";

/**
 * Keyboard Shortcuts Table
 *
 * Reusable component showing keyboard shortcuts.
 * Used by both the documentation page and the keyboard shortcuts modal.
 */

interface Shortcut {
  keys: string[];
  description: string;
  category: "Navigation" | "Chat" | "General";
}

export const shortcuts: Shortcut[] = [
  // Navigation
  { keys: ["Ctrl", "K"], description: "Open search", category: "Navigation" },
  { keys: ["Ctrl", "B"], description: "Toggle sidebar", category: "Navigation" },
  { keys: ["Ctrl", "Shift", "A"], description: "Go to admin panel", category: "Navigation" },
  { keys: ["Ctrl", "Shift", "S"], description: "Go to settings", category: "Navigation" },

  // Chat
  { keys: ["Ctrl", "N"], description: "New chat", category: "Chat" },
  { keys: ["Ctrl", "/"], description: "Focus message input", category: "Chat" },
  { keys: ["Ctrl", "Enter"], description: "Send message", category: "Chat" },
  { keys: ["↑"], description: "Edit last message (when input empty)", category: "Chat" },
  { keys: ["Ctrl", "Shift", "C"], description: "Copy last response", category: "Chat" },

  // General
  { keys: ["Esc"], description: "Close modals/dialogs", category: "General" },
  { keys: ["Ctrl", "?"], description: "Show keyboard shortcuts", category: "General" },
  { keys: ["Ctrl", ","], description: "Open settings", category: "General" },
];

interface KeyboardShortcutsTableProps {
  className?: string;
}

export function KeyboardShortcutsTable({ className }: KeyboardShortcutsTableProps) {
  // Group shortcuts by category
  const groupedShortcuts = shortcuts.reduce((acc, shortcut) => {
    if (!acc[shortcut.category]) {
      acc[shortcut.category] = [];
    }
    acc[shortcut.category].push(shortcut);
    return acc;
  }, {} as Record<string, Shortcut[]>);

  return (
    <div className={className}>
      {Object.entries(groupedShortcuts).map(([category, items]) => (
        <div key={category} className="mb-8 last:mb-0">
          <h3 className="text-lg font-semibold mb-4">{category}</h3>
          <div className="space-y-3">
            {items.map((shortcut, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors"
              >
                <span className="text-sm text-foreground">{shortcut.description}</span>
                <div className="flex gap-1">
                  {shortcut.keys.map((key, j) => (
                    <kbd
                      key={j}
                      className="px-2 py-1 text-xs font-mono bg-muted border border-border rounded shadow-sm"
                    >
                      {key}
                    </kbd>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
