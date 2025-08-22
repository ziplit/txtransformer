import * as fs from "fs-extra";
import * as path from "path";
import * as crypto from "crypto";
import { StorageAdapter } from "../types";

export class FilesystemStorageAdapter implements StorageAdapter {
  private basePath: string;

  constructor(basePath: string = "./temp") {
    this.basePath = path.resolve(basePath);
  }

  /**
   * Initialize storage directory
   */
  async initialize(): Promise<void> {
    await fs.ensureDir(this.basePath);
  }

  /**
   * Store data and return the storage key
   */
  async store(key: string, data: Buffer): Promise<string> {
    await this.initialize();

    const filePath = this.getFilePath(key);
    await fs.ensureDir(path.dirname(filePath));
    await fs.writeFile(filePath, data);

    return key;
  }

  /**
   * Retrieve data by key
   */
  async retrieve(key: string): Promise<Buffer> {
    const filePath = this.getFilePath(key);

    if (!(await this.exists(key))) {
      throw new Error(`File not found: ${key}`);
    }

    return await fs.readFile(filePath);
  }

  /**
   * Delete data by key
   */
  async delete(key: string): Promise<void> {
    const filePath = this.getFilePath(key);

    if (await this.exists(key)) {
      await fs.remove(filePath);
    }
  }

  /**
   * Check if data exists
   */
  async exists(key: string): Promise<boolean> {
    const filePath = this.getFilePath(key);
    return await fs.pathExists(filePath);
  }

  /**
   * Generate file hash for caching
   */
  generateHash(data: Buffer): string {
    return crypto.createHash("sha256").update(data).digest("hex");
  }

  /**
   * Store with auto-generated hash key
   */
  async storeWithHash(data: Buffer): Promise<string> {
    const hash = this.generateHash(data);
    await this.store(hash, data);
    return hash;
  }

  /**
   * Clean up old files (older than specified days)
   */
  async cleanup(maxAgeInDays: number = 7): Promise<number> {
    await this.initialize();

    const cutoffTime = Date.now() - maxAgeInDays * 24 * 60 * 60 * 1000;
    let deletedCount = 0;

    const cleanupDir = async (dirPath: string) => {
      const items = await fs.readdir(dirPath, { withFileTypes: true });

      for (const item of items) {
        const itemPath = path.join(dirPath, item.name);

        if (item.isDirectory()) {
          await cleanupDir(itemPath);

          // Remove empty directories
          const remaining = await fs.readdir(itemPath);
          if (remaining.length === 0) {
            await fs.remove(itemPath);
          }
        } else {
          const stats = await fs.stat(itemPath);
          if (stats.mtime.getTime() < cutoffTime) {
            await fs.remove(itemPath);
            deletedCount++;
          }
        }
      }
    };

    await cleanupDir(this.basePath);
    return deletedCount;
  }

  /**
   * Get storage statistics
   */
  async getStats(): Promise<{
    totalFiles: number;
    totalSize: number;
    oldestFile?: Date;
    newestFile?: Date;
  }> {
    await this.initialize();

    let totalFiles = 0;
    let totalSize = 0;
    let oldestFile: Date | undefined;
    let newestFile: Date | undefined;

    const scanDir = async (dirPath: string) => {
      try {
        const items = await fs.readdir(dirPath, { withFileTypes: true });

        for (const item of items) {
          const itemPath = path.join(dirPath, item.name);

          if (item.isDirectory()) {
            await scanDir(itemPath);
          } else {
            const stats = await fs.stat(itemPath);
            totalFiles++;
            totalSize += stats.size;

            if (!oldestFile || stats.mtime < oldestFile) {
              oldestFile = stats.mtime;
            }
            if (!newestFile || stats.mtime > newestFile) {
              newestFile = stats.mtime;
            }
          }
        }
      } catch (error) {
        // Directory might not exist yet
      }
    };

    await scanDir(this.basePath);

    return {
      totalFiles,
      totalSize,
      oldestFile,
      newestFile,
    };
  }

  /**
   * Get file path from key
   */
  private getFilePath(key: string): string {
    // Sanitize key to prevent directory traversal
    const sanitizedKey = key.replace(/[^a-zA-Z0-9._-]/g, "_");

    // Create subdirectories based on first few characters for better performance
    const subDir =
      sanitizedKey.length >= 2 ? sanitizedKey.substring(0, 2) : "default";

    return path.join(this.basePath, subDir, sanitizedKey);
  }
}
