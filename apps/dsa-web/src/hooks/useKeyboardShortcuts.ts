import { useEffect } from 'react';

type ShortcutAction = {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  handler: () => void;
  description: string;
};

/**
 * Global keyboard shortcuts hook.
 * Ctrl+K: focus search
 * Ctrl+1-9: navigate pages (handled externally)
 * Esc: close modals (handled by components)
 * R: refresh data (handled by components)
 */
export function useKeyboardShortcuts(shortcuts: ShortcutAction[]) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable;

      if (isInput && e.key !== 'Escape') return;

      for (const shortcut of shortcuts) {
        const ctrlMatch = shortcut.ctrlKey ? (e.ctrlKey || e.metaKey) : true;
        const metaMatch = shortcut.metaKey ? e.metaKey : true;
        if (e.key === shortcut.key && ctrlMatch && metaMatch) {
          e.preventDefault();
          shortcut.handler();
          return;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
}
