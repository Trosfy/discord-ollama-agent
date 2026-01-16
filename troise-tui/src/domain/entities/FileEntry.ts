/**
 * FileEntry entity - represents a file or directory in the file browser.
 */
export interface FileEntry {
  name: string;
  path: string;
  isDirectory: boolean;
  size?: number;
  modifiedAt?: Date;
  /** Git status if in a git repo */
  gitStatus?: GitStatus;
  /** File extension (without dot) */
  extension?: string;
  /** MIME type */
  mimetype?: string;
  /** Whether file is hidden (starts with .) */
  hidden: boolean;
  /** Children if directory is expanded */
  children?: FileEntry[];
  /** Whether directory is expanded in tree view */
  expanded?: boolean;
  /** Depth in tree (0 = root) */
  depth: number;
}

export type GitStatus =
  | "modified"    // M - Modified
  | "added"       // A - Added
  | "deleted"     // D - Deleted
  | "renamed"     // R - Renamed
  | "copied"      // C - Copied
  | "untracked"   // ? - Untracked
  | "ignored"     // ! - Ignored
  | "unmerged"    // U - Unmerged
  | "clean";      // No changes

/**
 * Get file icon based on type/extension
 */
export function getFileIcon(entry: FileEntry): string {
  if (entry.isDirectory) {
    return entry.expanded ? "📂" : "📁";
  }

  const iconMap: Record<string, string> = {
    // Code
    ts: "📘",
    tsx: "📘",
    js: "📒",
    jsx: "📒",
    py: "🐍",
    rs: "🦀",
    go: "🐹",
    java: "☕",
    rb: "💎",
    php: "🐘",
    c: "🔧",
    cpp: "🔧",
    h: "🔧",
    cs: "🟣",
    swift: "🍎",
    kt: "🟠",

    // Web
    html: "🌐",
    css: "🎨",
    scss: "🎨",
    less: "🎨",

    // Data
    json: "📋",
    yaml: "📋",
    yml: "📋",
    toml: "📋",
    xml: "📋",
    csv: "📊",

    // Docs
    md: "📝",
    txt: "📄",
    pdf: "📕",
    doc: "📘",
    docx: "📘",

    // Config
    env: "🔐",
    gitignore: "🙈",
    dockerignore: "🐳",

    // Build
    dockerfile: "🐳",
    makefile: "🔨",

    // Images
    png: "🖼️",
    jpg: "🖼️",
    jpeg: "🖼️",
    gif: "🖼️",
    svg: "🖼️",
    ico: "🖼️",

    // Lock files
    lock: "🔒",
  };

  const ext = entry.extension?.toLowerCase() || "";
  return iconMap[ext] || "📄";
}

/**
 * Get git status indicator
 */
export function getGitStatusIndicator(status?: GitStatus): string {
  const indicators: Record<GitStatus, string> = {
    modified: "M",
    added: "A",
    deleted: "D",
    renamed: "R",
    copied: "C",
    untracked: "?",
    ignored: "!",
    unmerged: "U",
    clean: "✓",
  };
  return status ? indicators[status] : "";
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes?: number): string {
  if (bytes === undefined) return "";

  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = bytes;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

/**
 * Sort file entries (directories first, then alphabetically)
 */
export function sortFileEntries(entries: FileEntry[]): FileEntry[] {
  return [...entries].sort((a, b) => {
    // Directories first
    if (a.isDirectory && !b.isDirectory) return -1;
    if (!a.isDirectory && b.isDirectory) return 1;

    // Hidden files last within their category
    if (a.hidden && !b.hidden) return 1;
    if (!a.hidden && b.hidden) return -1;

    // Alphabetical
    return a.name.localeCompare(b.name);
  });
}

/**
 * Create a FileEntry from filesystem stats
 */
export function createFileEntry(
  name: string,
  path: string,
  isDirectory: boolean,
  depth: number,
  stats?: { size?: number; modifiedAt?: Date }
): FileEntry {
  const extension = !isDirectory ? name.split(".").pop() : undefined;

  return {
    name,
    path,
    isDirectory,
    size: stats?.size,
    modifiedAt: stats?.modifiedAt,
    extension,
    hidden: name.startsWith("."),
    depth,
    expanded: false,
  };
}
