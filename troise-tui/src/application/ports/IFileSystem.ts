import type { FileEntry } from "@domain/entities";

/**
 * File system interface for local file operations.
 */
export interface IFileSystem {
  /**
   * Read file content as text
   */
  readFile(path: string): Promise<string>;

  /**
   * Read file content as buffer
   */
  readFileBuffer(path: string): Promise<Buffer>;

  /**
   * Write content to file
   */
  writeFile(path: string, content: string | Buffer): Promise<void>;

  /**
   * Check if file/directory exists
   */
  exists(path: string): Promise<boolean>;

  /**
   * Check if path is a directory
   */
  isDirectory(path: string): Promise<boolean>;

  /**
   * List directory contents
   */
  listDirectory(path: string, options?: ListOptions): Promise<FileEntry[]>;

  /**
   * Get file stats
   */
  getStats(path: string): Promise<FileStats>;

  /**
   * Create directory (recursive)
   */
  createDirectory(path: string): Promise<void>;

  /**
   * Delete file or directory
   */
  delete(path: string, recursive?: boolean): Promise<void>;

  /**
   * Copy file or directory
   */
  copy(source: string, destination: string): Promise<void>;

  /**
   * Move/rename file or directory
   */
  move(source: string, destination: string): Promise<void>;

  /**
   * Watch for file changes
   */
  watch(
    path: string,
    callback: (event: FileChangeEvent) => void
  ): () => void;

  /**
   * Resolve path (expand ~, resolve relative)
   */
  resolvePath(path: string): string;

  /**
   * Get home directory
   */
  getHomeDir(): string;

  /**
   * Get current working directory
   */
  getCwd(): string;
}

export interface ListOptions {
  /** Include hidden files (starting with .) */
  includeHidden?: boolean;
  /** Maximum depth for recursive listing */
  maxDepth?: number;
  /** Filter by file extension */
  extensions?: string[];
  /** Ignore patterns (glob) */
  ignore?: string[];
}

export interface FileStats {
  size: number;
  createdAt: Date;
  modifiedAt: Date;
  isDirectory: boolean;
  isFile: boolean;
  isSymlink: boolean;
  permissions: string;
}

export interface FileChangeEvent {
  type: "add" | "change" | "unlink" | "addDir" | "unlinkDir";
  path: string;
}
