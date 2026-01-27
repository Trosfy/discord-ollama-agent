/**
 * FileHandlerAdapter
 *
 * Decodes and manages file artifacts received from troise-ai.
 * Handles base64 decoding, Blob creation, and Object URL management.
 */

import type { IncomingFile, DecodedFile } from "@/core/types/file.types";

/**
 * MIME type mapping from file extensions
 */
const MIME_TYPE_MAP: Record<string, string> = {
  // Code files
  py: "text/x-python",
  js: "text/javascript",
  ts: "text/typescript",
  tsx: "text/typescript",
  jsx: "text/javascript",
  json: "application/json",
  html: "text/html",
  css: "text/css",
  scss: "text/scss",
  yaml: "text/yaml",
  yml: "text/yaml",
  toml: "text/toml",
  xml: "application/xml",
  sql: "text/x-sql",
  sh: "text/x-shellscript",
  bash: "text/x-shellscript",
  rs: "text/x-rust",
  go: "text/x-go",
  java: "text/x-java",
  c: "text/x-c",
  cpp: "text/x-c++",
  h: "text/x-c",
  hpp: "text/x-c++",
  // Text files
  md: "text/markdown",
  txt: "text/plain",
  csv: "text/csv",
  // Documents
  pdf: "application/pdf",
  // Images
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  gif: "image/gif",
  webp: "image/webp",
  svg: "image/svg+xml",
  // Archives
  zip: "application/zip",
  tar: "application/x-tar",
  gz: "application/gzip",
};

export class FileHandlerAdapter {
  private objectUrls: string[] = [];

  /**
   * Decode base64 file to Blob with Object URL
   *
   * @param file - Incoming file from WebSocket
   * @returns Decoded file with Blob and Object URL
   */
  decode(file: IncomingFile): DecodedFile {
    // Decode base64 to binary
    const binaryString = atob(file.base64Data);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    // Determine MIME type
    const mimeType = file.mimeType || this.inferMimeType(file.filename);

    // Create Blob and Object URL
    const blob = new Blob([bytes], { type: mimeType });
    const url = URL.createObjectURL(blob);

    // Track URL for cleanup
    this.objectUrls.push(url);

    return {
      filename: file.filename,
      blob,
      url,
      source: file.source,
      confidence: file.confidence,
      filepath: file.filepath,
    };
  }

  /**
   * Decode multiple files
   *
   * @param files - Array of incoming files
   * @returns Array of decoded files
   */
  decodeAll(files: IncomingFile[]): DecodedFile[] {
    return files.map((file) => this.decode(file));
  }

  /**
   * Clean up Object URLs to prevent memory leaks
   * Call this when component unmounts or files are no longer needed
   */
  cleanup(): void {
    this.objectUrls.forEach((url) => {
      try {
        URL.revokeObjectURL(url);
      } catch {
        // Ignore errors if URL was already revoked
      }
    });
    this.objectUrls = [];
  }

  /**
   * Revoke a specific Object URL
   *
   * @param url - Object URL to revoke
   */
  revokeUrl(url: string): void {
    const index = this.objectUrls.indexOf(url);
    if (index !== -1) {
      URL.revokeObjectURL(url);
      this.objectUrls.splice(index, 1);
    }
  }

  /**
   * Get the number of tracked Object URLs
   */
  get trackedUrlCount(): number {
    return this.objectUrls.length;
  }

  /**
   * Infer MIME type from filename extension
   *
   * @param filename - File name with extension
   * @returns MIME type string
   */
  private inferMimeType(filename: string): string {
    const ext = filename.split(".").pop()?.toLowerCase();
    return MIME_TYPE_MAP[ext || ""] || "application/octet-stream";
  }

  /**
   * Trigger browser download for a decoded file
   *
   * @param file - Decoded file to download
   */
  static downloadFile(file: DecodedFile): void {
    const link = document.createElement("a");
    link.href = file.url;
    link.download = file.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  /**
   * Check if file is previewable in browser
   *
   * @param file - Decoded file or filename
   * @returns true if file can be previewed
   */
  static isPreviewable(file: DecodedFile | string): boolean {
    const filename = typeof file === "string" ? file : file.filename;
    const ext = filename.split(".").pop()?.toLowerCase();

    // Images and PDFs are previewable
    const previewableTypes = ["png", "jpg", "jpeg", "gif", "webp", "svg", "pdf"];
    return previewableTypes.includes(ext || "");
  }

  /**
   * Check if file is a code/text file
   *
   * @param file - Decoded file or filename
   * @returns true if file is code/text
   */
  static isCodeFile(file: DecodedFile | string): boolean {
    const filename = typeof file === "string" ? file : file.filename;
    const ext = filename.split(".").pop()?.toLowerCase();

    const codeTypes = [
      "py", "js", "ts", "tsx", "jsx", "json", "html", "css", "scss",
      "yaml", "yml", "toml", "xml", "sql", "sh", "bash", "rs", "go",
      "java", "c", "cpp", "h", "hpp", "md", "txt", "csv",
    ];
    return codeTypes.includes(ext || "");
  }
}
