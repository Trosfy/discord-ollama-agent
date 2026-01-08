/**
 * File Storage Service
 *
 * Stores uploaded files in IndexedDB for local access.
 * Uses TTL for automatic cleanup of old files.
 *
 * SOLID Principles:
 * - Single Responsibility: Only handles file storage in browser
 * - Open/Closed: Can be extended for different storage backends
 */

const DB_NAME = "chat-files";
const DB_VERSION = 1;
const STORE_NAME = "files";
const DEFAULT_TTL_HOURS = 24; // Files expire after 24 hours

export interface StoredFile {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
  blob: Blob;
  previewUrl?: string;
  createdAt: number;
  expiresAt: number;
}

export interface StoredFileMeta {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
  createdAt: number;
  expiresAt: number;
}

/**
 * Opens the IndexedDB database
 */
function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "id" });
        store.createIndex("expiresAt", "expiresAt", { unique: false });
        store.createIndex("filename", "filename", { unique: false });
      }
    };
  });
}

export class FileStorageService {
  /**
   * Store a file in IndexedDB
   */
  static async storeFile(
    id: string,
    file: File | Blob,
    filename: string,
    ttlHours: number = DEFAULT_TTL_HOURS
  ): Promise<StoredFileMeta> {
    const db = await openDB();
    const now = Date.now();
    
    const storedFile: StoredFile = {
      id,
      filename,
      mimeType: file.type || "application/octet-stream",
      size: file.size,
      blob: file,
      createdAt: now,
      expiresAt: now + ttlHours * 60 * 60 * 1000,
    };

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.put(storedFile);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        resolve({
          id: storedFile.id,
          filename: storedFile.filename,
          mimeType: storedFile.mimeType,
          size: storedFile.size,
          createdAt: storedFile.createdAt,
          expiresAt: storedFile.expiresAt,
        });
      };
    });
  }

  /**
   * Get a file from IndexedDB
   */
  static async getFile(id: string): Promise<StoredFile | null> {
    const db = await openDB();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readonly");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(id);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const file = request.result as StoredFile | undefined;
        
        if (!file) {
          resolve(null);
          return;
        }

        // Check if expired
        if (file.expiresAt < Date.now()) {
          // Delete expired file
          this.deleteFile(id).catch(console.error);
          resolve(null);
          return;
        }

        resolve(file);
      };
    });
  }

  /**
   * Get file metadata without the blob
   */
  static async getFileMeta(id: string): Promise<StoredFileMeta | null> {
    const file = await this.getFile(id);
    if (!file) return null;

    return {
      id: file.id,
      filename: file.filename,
      mimeType: file.mimeType,
      size: file.size,
      createdAt: file.createdAt,
      expiresAt: file.expiresAt,
    };
  }

  /**
   * Delete a file from IndexedDB
   */
  static async deleteFile(id: string): Promise<void> {
    const db = await openDB();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.delete(id);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  }

  /**
   * Open a stored file in a new browser tab/window
   */
  static async openFile(id: string): Promise<boolean> {
    const file = await this.getFile(id);
    if (!file) return false;

    const url = URL.createObjectURL(file.blob);
    window.open(url, "_blank");
    
    // Revoke URL after a delay to allow the browser to load it
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    
    return true;
  }

  /**
   * Download a stored file
   */
  static async downloadFile(id: string): Promise<boolean> {
    const file = await this.getFile(id);
    if (!file) return false;

    const url = URL.createObjectURL(file.blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    return true;
  }

  /**
   * Clean up expired files
   */
  static async cleanupExpired(): Promise<number> {
    const db = await openDB();
    const now = Date.now();
    let deletedCount = 0;

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const index = store.index("expiresAt");
      
      // Get all files that have expired
      const range = IDBKeyRange.upperBound(now);
      const request = index.openCursor(range);

      request.onerror = () => reject(request.error);
      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
        
        if (cursor) {
          cursor.delete();
          deletedCount++;
          cursor.continue();
        } else {
          console.log(`[FileStorage] Cleaned up ${deletedCount} expired files`);
          resolve(deletedCount);
        }
      };
    });
  }

  /**
   * Get all stored files metadata (for debugging/admin)
   */
  static async getAllFiles(): Promise<StoredFileMeta[]> {
    const db = await openDB();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readonly");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const files = (request.result as StoredFile[])
          .filter((f) => f.expiresAt > Date.now())
          .map((f) => ({
            id: f.id,
            filename: f.filename,
            mimeType: f.mimeType,
            size: f.size,
            createdAt: f.createdAt,
            expiresAt: f.expiresAt,
          }));
        resolve(files);
      };
    });
  }

  /**
   * Clear all stored files
   */
  static async clearAll(): Promise<void> {
    const db = await openDB();

    return new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.clear();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  }
}

// Run cleanup on module load (client-side only)
if (typeof window !== "undefined") {
  FileStorageService.cleanupExpired().catch(console.error);
}
