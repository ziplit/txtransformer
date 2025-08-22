import * as fs from "fs-extra";
import * as path from "path";
import { StorageAdapter } from "../types";
import { FilesystemStorageAdapter } from "./filesystem";

export interface CleanupOptions {
  /** Maximum age in days for files to be kept */
  maxAgeInDays?: number;
  /** Patterns to exclude from cleanup */
  excludePatterns?: string[];
  /** Dry run mode - only report what would be deleted */
  dryRun?: boolean;
  /** Include subdirectories in cleanup */
  recursive?: boolean;
}

export interface CleanupResult {
  /** Number of files deleted */
  filesDeleted: number;
  /** Number of directories removed */
  directoriesRemoved: number;
  /** Total bytes freed */
  bytesFreed: number;
  /** List of deleted file paths (if requested) */
  deletedPaths?: string[];
  /** Any errors encountered during cleanup */
  errors: string[];
}

/**
 * Utility class for managing temporary file cleanup
 */
export class CleanupManager {
  private tempDirs: Set<string> = new Set();
  private storageAdapters: StorageAdapter[] = [];

  /**
   * Register a temporary directory for cleanup
   */
  registerTempDirectory(dirPath: string): void {
    this.tempDirs.add(path.resolve(dirPath));
  }

  /**
   * Register a storage adapter for cleanup
   */
  registerStorageAdapter(adapter: StorageAdapter): void {
    this.storageAdapters.push(adapter);
  }

  /**
   * Clean up temporary files and directories
   */
  async cleanup(options: CleanupOptions = {}): Promise<CleanupResult> {
    const {
      maxAgeInDays = 7,
      excludePatterns = [],
      dryRun = false,
      recursive = true,
    } = options;

    const result: CleanupResult = {
      filesDeleted: 0,
      directoriesRemoved: 0,
      bytesFreed: 0,
      deletedPaths: [],
      errors: [],
    };

    // Clean up registered temporary directories
    for (const tempDir of this.tempDirs) {
      try {
        const dirResult = await this.cleanupDirectory(tempDir, {
          maxAgeInDays,
          excludePatterns,
          dryRun,
          recursive,
        });

        result.filesDeleted += dirResult.filesDeleted;
        result.directoriesRemoved += dirResult.directoriesRemoved;
        result.bytesFreed += dirResult.bytesFreed;
        if (dirResult.deletedPaths) {
          result.deletedPaths!.push(...dirResult.deletedPaths);
        }
        result.errors.push(...dirResult.errors);
      } catch (error) {
        result.errors.push(`Failed to cleanup directory ${tempDir}: ${error}`);
      }
    }

    // Clean up storage adapters that support cleanup
    for (const adapter of this.storageAdapters) {
      if (adapter instanceof FilesystemStorageAdapter) {
        try {
          const deletedCount = await adapter.cleanup(maxAgeInDays);
          result.filesDeleted += deletedCount;
        } catch (error) {
          result.errors.push(`Failed to cleanup storage adapter: ${error}`);
        }
      }
    }

    return result;
  }

  /**
   * Clean up a specific directory
   */
  async cleanupDirectory(
    dirPath: string,
    options: CleanupOptions = {},
  ): Promise<CleanupResult> {
    const {
      maxAgeInDays = 7,
      excludePatterns = [],
      dryRun = false,
      recursive = true,
    } = options;

    const result: CleanupResult = {
      filesDeleted: 0,
      directoriesRemoved: 0,
      bytesFreed: 0,
      deletedPaths: [],
      errors: [],
    };

    if (!(await fs.pathExists(dirPath))) {
      return result;
    }

    const cutoffTime = Date.now() - maxAgeInDays * 24 * 60 * 60 * 1000;

    const processDirectory = async (currentDir: string) => {
      try {
        const items = await fs.readdir(currentDir, { withFileTypes: true });

        for (const item of items) {
          const itemPath = path.join(currentDir, item.name);

          // Check if item matches exclude patterns
          if (this.shouldExclude(itemPath, excludePatterns)) {
            continue;
          }

          if (item.isDirectory()) {
            if (recursive) {
              await processDirectory(itemPath);
            }

            // Check if directory is empty and should be removed
            try {
              const remaining = await fs.readdir(itemPath);
              if (remaining.length === 0) {
                if (!dryRun) {
                  await fs.remove(itemPath);
                }
                result.directoriesRemoved++;
                result.deletedPaths?.push(itemPath);
              }
            } catch (error) {
              result.errors.push(
                `Failed to check directory ${itemPath}: ${error}`,
              );
            }
          } else {
            try {
              const stats = await fs.stat(itemPath);
              if (stats.mtime.getTime() < cutoffTime) {
                if (!dryRun) {
                  await fs.remove(itemPath);
                }
                result.filesDeleted++;
                result.bytesFreed += stats.size;
                result.deletedPaths?.push(itemPath);
              }
            } catch (error) {
              result.errors.push(
                `Failed to process file ${itemPath}: ${error}`,
              );
            }
          }
        }
      } catch (error) {
        result.errors.push(`Failed to read directory ${currentDir}: ${error}`);
      }
    };

    await processDirectory(dirPath);
    return result;
  }

  /**
   * Check if a path should be excluded from cleanup
   */
  private shouldExclude(filePath: string, excludePatterns: string[]): boolean {
    const fileName = path.basename(filePath);
    const relativePath = path.relative(process.cwd(), filePath);

    return excludePatterns.some((pattern) => {
      // Simple glob-like matching
      const regex = new RegExp(
        "^" +
          pattern
            .replace(/\*/g, ".*")
            .replace(/\?/g, ".")
            .replace(/\./g, "\\.") +
          "$",
      );

      return regex.test(fileName) || regex.test(relativePath);
    });
  }

  /**
   * Get cleanup statistics without actually deleting files
   */
  async getCleanupStats(options: CleanupOptions = {}): Promise<CleanupResult> {
    return this.cleanup({ ...options, dryRun: true });
  }

  /**
   * Schedule automatic cleanup at regular intervals
   */
  scheduleCleanup(
    intervalHours: number = 24,
    options: CleanupOptions = {},
  ): NodeJS.Timeout {
    const intervalMs = intervalHours * 60 * 60 * 1000;

    return setInterval(async () => {
      try {
        await this.cleanup(options);
      } catch (error) {
        console.error("Scheduled cleanup failed:", error);
      }
    }, intervalMs);
  }

  /**
   * Clear all registered directories and adapters
   */
  clear(): void {
    this.tempDirs.clear();
    this.storageAdapters.length = 0;
  }
}

// Export singleton instance for convenience
export const cleanupManager = new CleanupManager();
