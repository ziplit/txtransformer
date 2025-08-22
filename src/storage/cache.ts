import * as crypto from "crypto";
import { StorageAdapter } from "../types";

export interface CacheEntry<T = any> {
  /** Cached data */
  data: T;
  /** Timestamp when cached */
  timestamp: number;
  /** TTL in milliseconds */
  ttl?: number;
  /** File hash that this cache entry is based on */
  fileHash: string;
  /** Metadata about the cached item */
  metadata?: Record<string, any>;
}

export interface CacheOptions {
  /** Default TTL in milliseconds */
  defaultTtl?: number;
  /** Maximum cache size (number of entries) */
  maxSize?: number;
  /** Key prefix for cache entries */
  keyPrefix?: string;
}

/**
 * Hash-based cache that stores processed file results
 */
export class FileHashCache {
  private storage: StorageAdapter;
  private options: Required<CacheOptions>;
  private cacheKeys = new Set<string>();

  constructor(storage: StorageAdapter, options: CacheOptions = {}) {
    this.storage = storage;
    this.options = {
      defaultTtl: 24 * 60 * 60 * 1000, // 24 hours
      maxSize: 10000,
      keyPrefix: "cache:",
      ...options,
    };
  }

  /**
   * Generate hash for file content
   */
  generateFileHash(content: Buffer): string {
    return crypto.createHash("sha256").update(content).digest("hex");
  }

  /**
   * Generate cache key from file hash and additional identifier
   */
  private generateCacheKey(fileHash: string, identifier?: string): string {
    const key = identifier ? `${fileHash}:${identifier}` : fileHash;
    return `${this.options.keyPrefix}${key}`;
  }

  /**
   * Store processed result in cache
   */
  async set<T>(
    fileHash: string,
    data: T,
    options: {
      identifier?: string;
      ttl?: number;
      metadata?: Record<string, any>;
    } = {},
  ): Promise<void> {
    const { identifier, ttl = this.options.defaultTtl, metadata } = options;
    const cacheKey = this.generateCacheKey(fileHash, identifier);

    const entry: CacheEntry<T> = {
      data,
      timestamp: Date.now(),
      ttl,
      fileHash,
      metadata,
    };

    // Enforce cache size limit
    if (this.cacheKeys.size >= this.options.maxSize) {
      await this.evictLeastRecentlyUsed();
    }

    const serialized = Buffer.from(JSON.stringify(entry), "utf-8");
    await this.storage.store(cacheKey, serialized);
    this.cacheKeys.add(cacheKey);
  }

  /**
   * Retrieve cached result by file hash
   */
  async get<T>(fileHash: string, identifier?: string): Promise<T | null> {
    const cacheKey = this.generateCacheKey(fileHash, identifier);

    try {
      if (!(await this.storage.exists(cacheKey))) {
        return null;
      }

      const serialized = await this.storage.retrieve(cacheKey);
      const entry: CacheEntry<T> = JSON.parse(serialized.toString("utf-8"));

      // Check if entry has expired
      if (entry.ttl && Date.now() - entry.timestamp > entry.ttl) {
        await this.delete(fileHash, identifier);
        return null;
      }

      return entry.data;
    } catch (error) {
      // Cache miss or corrupted data
      await this.delete(fileHash, identifier);
      return null;
    }
  }

  /**
   * Check if file content is cached
   */
  async has(fileHash: string, identifier?: string): Promise<boolean> {
    const cacheKey = this.generateCacheKey(fileHash, identifier);

    if (!this.cacheKeys.has(cacheKey)) {
      return false;
    }

    // Verify entry still exists and is valid
    const data = await this.get(fileHash, identifier);
    return data !== null;
  }

  /**
   * Delete cached entry
   */
  async delete(fileHash: string, identifier?: string): Promise<void> {
    const cacheKey = this.generateCacheKey(fileHash, identifier);

    try {
      await this.storage.delete(cacheKey);
    } catch (error) {
      // Ignore deletion errors
    }

    this.cacheKeys.delete(cacheKey);
  }

  /**
   * Get or compute cached value
   */
  async getOrCompute<T>(
    fileContent: Buffer,
    computeFn: (content: Buffer) => Promise<T>,
    options: {
      identifier?: string;
      ttl?: number;
      metadata?: Record<string, any>;
    } = {},
  ): Promise<T> {
    const fileHash = this.generateFileHash(fileContent);

    // Try to get from cache first
    const cached = await this.get<T>(fileHash, options.identifier);
    if (cached !== null) {
      return cached;
    }

    // Compute and cache result
    const result = await computeFn(fileContent);
    await this.set(fileHash, result, options);

    return result;
  }

  /**
   * Clear all cache entries
   */
  async clear(): Promise<void> {
    const deletePromises = Array.from(this.cacheKeys).map(async (key) => {
      try {
        await this.storage.delete(key);
      } catch (error) {
        // Ignore deletion errors
      }
    });

    await Promise.all(deletePromises);
    this.cacheKeys.clear();
  }

  /**
   * Get cache statistics
   */
  async getStats(): Promise<{
    size: number;
    totalEntries: number;
    expiredEntries: number;
  }> {
    let totalEntries = 0;
    let expiredEntries = 0;
    const now = Date.now();

    for (const cacheKey of this.cacheKeys) {
      try {
        if (await this.storage.exists(cacheKey)) {
          const serialized = await this.storage.retrieve(cacheKey);
          const entry: CacheEntry = JSON.parse(serialized.toString("utf-8"));

          totalEntries++;

          if (entry.ttl && now - entry.timestamp > entry.ttl) {
            expiredEntries++;
          }
        }
      } catch (error) {
        // Skip corrupted entries
      }
    }

    return {
      size: this.cacheKeys.size,
      totalEntries,
      expiredEntries,
    };
  }

  /**
   * Clean up expired entries
   */
  async cleanup(): Promise<number> {
    const now = Date.now();
    let cleanedCount = 0;
    const keysToRemove: string[] = [];

    for (const cacheKey of this.cacheKeys) {
      try {
        if (await this.storage.exists(cacheKey)) {
          const serialized = await this.storage.retrieve(cacheKey);
          const entry: CacheEntry = JSON.parse(serialized.toString("utf-8"));

          if (entry.ttl && now - entry.timestamp > entry.ttl) {
            await this.storage.delete(cacheKey);
            keysToRemove.push(cacheKey);
            cleanedCount++;
          }
        } else {
          // Storage entry doesn't exist, remove from our keys
          keysToRemove.push(cacheKey);
        }
      } catch (error) {
        // Remove corrupted entries
        keysToRemove.push(cacheKey);
        cleanedCount++;
      }
    }

    keysToRemove.forEach((key) => this.cacheKeys.delete(key));
    return cleanedCount;
  }

  /**
   * Evict least recently used entries when cache is full
   */
  private async evictLeastRecentlyUsed(): Promise<void> {
    const entriesToEvict = Math.max(1, Math.floor(this.options.maxSize * 0.1)); // Evict 10%
    const entries: Array<{ key: string; timestamp: number }> = [];

    // Collect timestamps for all entries
    for (const cacheKey of this.cacheKeys) {
      try {
        if (await this.storage.exists(cacheKey)) {
          const serialized = await this.storage.retrieve(cacheKey);
          const entry: CacheEntry = JSON.parse(serialized.toString("utf-8"));
          entries.push({ key: cacheKey, timestamp: entry.timestamp });
        }
      } catch (error) {
        // Remove corrupted entries
        this.cacheKeys.delete(cacheKey);
      }
    }

    // Sort by timestamp (oldest first) and evict
    entries.sort((a, b) => a.timestamp - b.timestamp);
    const toEvict = entries.slice(0, entriesToEvict);

    for (const { key } of toEvict) {
      try {
        await this.storage.delete(key);
      } catch (error) {
        // Ignore deletion errors
      }
      this.cacheKeys.delete(key);
    }
  }
}

/**
 * Specialized cache for different types of processed content
 */
export class ProcessingCache {
  private textCache: FileHashCache;
  private attachmentCache: FileHashCache;
  private ocrCache: FileHashCache;

  constructor(storage: StorageAdapter, options: CacheOptions = {}) {
    this.textCache = new FileHashCache(storage, {
      ...options,
      keyPrefix: "text:",
    });

    this.attachmentCache = new FileHashCache(storage, {
      ...options,
      keyPrefix: "attachment:",
    });

    this.ocrCache = new FileHashCache(storage, {
      ...options,
      keyPrefix: "ocr:",
      defaultTtl: 7 * 24 * 60 * 60 * 1000, // 7 days for OCR results
    });
  }

  /**
   * Cache extracted text content
   */
  async cacheTextExtraction(
    fileContent: Buffer,
    extractedText: string,
    metadata?: Record<string, any>,
  ): Promise<void> {
    await this.textCache.set(
      this.textCache.generateFileHash(fileContent),
      extractedText,
      { metadata },
    );
  }

  /**
   * Get cached text extraction
   */
  async getCachedTextExtraction(fileContent: Buffer): Promise<string | null> {
    const fileHash = this.textCache.generateFileHash(fileContent);
    return this.textCache.get<string>(fileHash);
  }

  /**
   * Cache OCR results
   */
  async cacheOcrResult(
    imageContent: Buffer,
    ocrText: string,
    confidence?: number,
  ): Promise<void> {
    await this.ocrCache.set(
      this.ocrCache.generateFileHash(imageContent),
      ocrText,
      { metadata: { confidence } },
    );
  }

  /**
   * Get cached OCR result
   */
  async getCachedOcrResult(imageContent: Buffer): Promise<string | null> {
    const fileHash = this.ocrCache.generateFileHash(imageContent);
    return this.ocrCache.get<string>(fileHash);
  }

  /**
   * Cache attachment processing results
   */
  async cacheAttachmentProcessing<T>(
    attachmentContent: Buffer,
    result: T,
    processingType: string,
  ): Promise<void> {
    await this.attachmentCache.set(
      this.attachmentCache.generateFileHash(attachmentContent),
      result,
      { identifier: processingType },
    );
  }

  /**
   * Get cached attachment processing result
   */
  async getCachedAttachmentProcessing<T>(
    attachmentContent: Buffer,
    processingType: string,
  ): Promise<T | null> {
    const fileHash = this.attachmentCache.generateFileHash(attachmentContent);
    return this.attachmentCache.get<T>(fileHash, processingType);
  }

  /**
   * Clean up all caches
   */
  async cleanup(): Promise<{ text: number; attachments: number; ocr: number }> {
    const [textCleaned, attachmentsCleaned, ocrCleaned] = await Promise.all([
      this.textCache.cleanup(),
      this.attachmentCache.cleanup(),
      this.ocrCache.cleanup(),
    ]);

    return {
      text: textCleaned,
      attachments: attachmentsCleaned,
      ocr: ocrCleaned,
    };
  }

  /**
   * Clear all caches
   */
  async clear(): Promise<void> {
    await Promise.all([
      this.textCache.clear(),
      this.attachmentCache.clear(),
      this.ocrCache.clear(),
    ]);
  }
}
