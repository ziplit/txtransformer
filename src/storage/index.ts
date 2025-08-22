import { StorageAdapter, TransformerConfig } from "../types";
import { FilesystemStorageAdapter } from "./filesystem";

/**
 * Memory storage adapter for testing and small datasets
 */
export class MemoryStorageAdapter implements StorageAdapter {
  private storage = new Map<string, Buffer>();

  async store(key: string, data: Buffer): Promise<string> {
    this.storage.set(key, data);
    return key;
  }

  async retrieve(key: string): Promise<Buffer> {
    const data = this.storage.get(key);
    if (!data) {
      throw new Error(`Data not found: ${key}`);
    }
    return data;
  }

  async delete(key: string): Promise<void> {
    this.storage.delete(key);
  }

  async exists(key: string): Promise<boolean> {
    return this.storage.has(key);
  }

  clear(): void {
    this.storage.clear();
  }

  size(): number {
    return this.storage.size;
  }
}

/**
 * Storage factory to create appropriate storage adapter based on configuration
 */
export class StorageFactory {
  static createStorageAdapter(config: TransformerConfig): StorageAdapter {
    const storageConfig = config.storage;

    if (!storageConfig) {
      // Default to filesystem storage in temp directory
      return new FilesystemStorageAdapter(config.tempDir);
    }

    switch (storageConfig.type) {
      case "memory":
        return new MemoryStorageAdapter();

      case "filesystem":
        return new FilesystemStorageAdapter(config.tempDir);

      case "custom":
        if (!storageConfig.adapter) {
          throw new Error("Custom storage adapter not provided");
        }
        return storageConfig.adapter;

      default:
        throw new Error(`Unknown storage type: ${storageConfig.type}`);
    }
  }
}

/**
 * Storage configuration utilities
 */
export class StorageConfig {
  /**
   * Create filesystem storage configuration
   */
  static filesystem(basePath?: string): TransformerConfig["storage"] {
    return {
      type: "filesystem",
      // The adapter will be created by StorageFactory
    };
  }

  /**
   * Create memory storage configuration
   */
  static memory(): TransformerConfig["storage"] {
    return {
      type: "memory",
    };
  }

  /**
   * Create custom storage configuration
   */
  static custom(adapter: StorageAdapter): TransformerConfig["storage"] {
    return {
      type: "custom",
      adapter,
    };
  }
}

// Re-export storage implementations
export { FilesystemStorageAdapter } from "./filesystem";
export { StorageAdapter } from "../types";
