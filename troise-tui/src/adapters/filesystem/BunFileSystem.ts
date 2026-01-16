import { readdir, stat, mkdir, rm, rename, cp } from "node:fs/promises";
import { join, resolve, dirname, basename, extname } from "node:path";
import { homedir } from "node:os";
import { watch } from "node:fs";
import type {
  IFileSystem,
  ListOptions,
  FileStats,
  FileChangeEvent,
} from "@application/ports";
import { createFileEntry, type FileEntry } from "@domain/entities";

/**
 * File system implementation using Bun's native APIs.
 */
export class BunFileSystem implements IFileSystem {
  async readFile(path: string): Promise<string> {
    const resolvedPath = this.resolvePath(path);
    const file = Bun.file(resolvedPath);

    if (!(await file.exists())) {
      throw new Error(`File not found: ${resolvedPath}`);
    }

    return await file.text();
  }

  async readFileBuffer(path: string): Promise<Buffer> {
    const resolvedPath = this.resolvePath(path);
    const file = Bun.file(resolvedPath);

    if (!(await file.exists())) {
      throw new Error(`File not found: ${resolvedPath}`);
    }

    const arrayBuffer = await file.arrayBuffer();
    return Buffer.from(arrayBuffer);
  }

  async writeFile(path: string, content: string | Buffer): Promise<void> {
    const resolvedPath = this.resolvePath(path);

    // Ensure directory exists
    const dir = dirname(resolvedPath);
    await this.createDirectory(dir);

    await Bun.write(resolvedPath, content);
  }

  async exists(path: string): Promise<boolean> {
    const resolvedPath = this.resolvePath(path);
    const file = Bun.file(resolvedPath);
    return await file.exists();
  }

  async isDirectory(path: string): Promise<boolean> {
    try {
      const resolvedPath = this.resolvePath(path);
      const stats = await stat(resolvedPath);
      return stats.isDirectory();
    } catch {
      return false;
    }
  }

  async listDirectory(
    path: string,
    options?: ListOptions
  ): Promise<FileEntry[]> {
    const resolvedPath = this.resolvePath(path);
    const entries: FileEntry[] = [];

    const dirEntries = await readdir(resolvedPath, { withFileTypes: true });

    for (const entry of dirEntries) {
      // Skip hidden files if not requested
      if (!options?.includeHidden && entry.name.startsWith(".")) {
        continue;
      }

      // Filter by extension
      if (options?.extensions?.length) {
        if (!entry.isDirectory()) {
          const ext = extname(entry.name).slice(1).toLowerCase();
          if (!options.extensions.includes(ext)) {
            continue;
          }
        }
      }

      // Check ignore patterns
      if (options?.ignore?.length) {
        const shouldIgnore = options.ignore.some((pattern) => {
          // Simple glob matching
          if (pattern.includes("*")) {
            const regex = new RegExp(
              "^" + pattern.replace(/\*/g, ".*").replace(/\?/g, ".") + "$"
            );
            return regex.test(entry.name);
          }
          return entry.name === pattern;
        });
        if (shouldIgnore) continue;
      }

      const entryPath = join(resolvedPath, entry.name);
      let fileStats: { size?: number; modifiedAt?: Date } | undefined;

      try {
        const stats = await stat(entryPath);
        fileStats = {
          size: stats.size,
          modifiedAt: stats.mtime,
        };
      } catch {
        // Stats unavailable
      }

      const fileEntry = createFileEntry(
        entry.name,
        entryPath,
        entry.isDirectory(),
        0,
        fileStats
      );

      entries.push(fileEntry);
    }

    return entries;
  }

  async getStats(path: string): Promise<FileStats> {
    const resolvedPath = this.resolvePath(path);
    const stats = await stat(resolvedPath);

    return {
      size: stats.size,
      createdAt: stats.birthtime,
      modifiedAt: stats.mtime,
      isDirectory: stats.isDirectory(),
      isFile: stats.isFile(),
      isSymlink: stats.isSymbolicLink(),
      permissions: stats.mode.toString(8).slice(-3),
    };
  }

  async createDirectory(path: string): Promise<void> {
    const resolvedPath = this.resolvePath(path);
    await mkdir(resolvedPath, { recursive: true });
  }

  async delete(path: string, recursive = false): Promise<void> {
    const resolvedPath = this.resolvePath(path);
    await rm(resolvedPath, { recursive, force: true });
  }

  async copy(source: string, destination: string): Promise<void> {
    const sourcePath = this.resolvePath(source);
    const destPath = this.resolvePath(destination);

    // Ensure destination directory exists
    await this.createDirectory(dirname(destPath));

    await cp(sourcePath, destPath, { recursive: true });
  }

  async move(source: string, destination: string): Promise<void> {
    const sourcePath = this.resolvePath(source);
    const destPath = this.resolvePath(destination);

    // Ensure destination directory exists
    await this.createDirectory(dirname(destPath));

    await rename(sourcePath, destPath);
  }

  watch(
    path: string,
    callback: (event: FileChangeEvent) => void
  ): () => void {
    const resolvedPath = this.resolvePath(path);

    const watcher = watch(
      resolvedPath,
      { recursive: true },
      (eventType, filename) => {
        if (!filename) return;

        const fullPath = join(resolvedPath, filename);
        const type =
          eventType === "rename"
            ? ("add" as const) // Could be add or unlink, simplified
            : ("change" as const);

        callback({
          type,
          path: fullPath,
        });
      }
    );

    return () => watcher.close();
  }

  resolvePath(path: string): string {
    // Expand ~ to home directory
    if (path.startsWith("~")) {
      path = join(homedir(), path.slice(1));
    }

    // Resolve to absolute path
    return resolve(path);
  }

  getHomeDir(): string {
    return homedir();
  }

  getCwd(): string {
    return process.cwd();
  }
}
