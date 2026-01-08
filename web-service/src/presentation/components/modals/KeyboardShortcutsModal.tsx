"use client";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { KeyboardShortcutsTable } from "@/components/docs/KeyboardShortcutsTable";
import { Keyboard } from "lucide-react";

/**
 * Keyboard Shortcuts Modal
 *
 * Modal dialog displaying all available keyboard shortcuts.
 * Reuses the KeyboardShortcutsTable component from the documentation page.
 */

interface KeyboardShortcutsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function KeyboardShortcutsModal({ open, onOpenChange }: KeyboardShortcutsModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-2xl">
            <Keyboard className="w-6 h-6" />
            Keyboard Shortcuts
          </DialogTitle>
          <DialogDescription>
            Speed up your workflow with these keyboard shortcuts
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4">
          <KeyboardShortcutsTable />
        </div>

        <div className="mt-6 p-4 bg-muted rounded-lg text-sm text-muted-foreground">
          <p>
            <strong>Note:</strong> Some shortcuts may not be fully implemented yet.
            We're actively working on adding more keyboard navigation features.
          </p>
          <p className="mt-2">
            Press <kbd className="px-2 py-1 text-xs bg-background border rounded">Esc</kbd> to close this dialog.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
