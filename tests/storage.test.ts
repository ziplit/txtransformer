import * as path from "path";
import { FilesystemStorageAdapter } from "../src/storage/filesystem";
import { MemoryStorageAdapter, StorageFactory } from "../src/storage";
import { FileHashCache } from "../src/storage/cache";
import { CleanupManager } from "../src/storage/cleanup";
import { TEST_TEMP_DIR } from "./setup";

describe("Storage Components", () => {
  describe("MemoryStorageAdapter", () => {
    let adapter: MemoryStorageAdapter;

    beforeEach(() => {
      adapter = new MemoryStorageAdapter();
    });

    test("should store and retrieve data", async () => {
      const key = "test-key";
      const data = Buffer.from("test data");

      const storedKey = await adapter.store(key, data);
      expect(storedKey).toBe(key);

      const retrieved = await adapter.retrieve(key);
      expect(retrieved).toEqual(data);
    });

    test("should check if key exists", async () => {
      const key = "test-key";
      const data = Buffer.from("test data");

      expect(await adapter.exists(key)).toBe(false);

      await adapter.store(key, data);
      expect(await adapter.exists(key)).toBe(true);
    });

    test("should delete data", async () => {
      const key = "test-key";
      const data = Buffer.from("test data");

      await adapter.store(key, data);
      expect(await adapter.exists(key)).toBe(true);

      await adapter.delete(key);
      expect(await adapter.exists(key)).toBe(false);
    });

    test("should throw error for non-existent key", async () => {
      await expect(adapter.retrieve("non-existent")).rejects.toThrow();
    });
  });

  describe("FilesystemStorageAdapter", () => {
    let adapter: FilesystemStorageAdapter;
    const testDir = path.join(TEST_TEMP_DIR, "filesystem-test");

    beforeEach(() => {
      adapter = new FilesystemStorageAdapter(testDir);
    });

    test("should store and retrieve data", async () => {
      const key = "test-file.txt";
      const data = Buffer.from("test file content");

      const storedKey = await adapter.store(key, data);
      expect(storedKey).toBe(key);

      const retrieved = await adapter.retrieve(key);
      expect(retrieved).toEqual(data);
    });

    test("should generate hash-based storage", async () => {
      const data = Buffer.from("test content for hashing");

      const hash = adapter.generateHash(data);
      const key = `${hash}.txt`;
      await adapter.store(key, data);

      expect(hash).toMatch(/^[a-f0-9]{64}$/);

      const retrieved = await adapter.retrieve(key);
      expect(retrieved).toEqual(data);
    });

    test("should handle file operations", async () => {
      await adapter.store("file1.txt", Buffer.from("content1"));
      await adapter.store("file2.txt", Buffer.from("content2"));

      expect(await adapter.exists("file1.txt")).toBe(true);
      expect(await adapter.exists("file2.txt")).toBe(true);
      expect(await adapter.exists("nonexistent.txt")).toBe(false);
    });
  });

  describe("StorageFactory", () => {
    test("should create memory storage adapter", () => {
      const config = {
        tempDir: TEST_TEMP_DIR,
        enableCaching: true,
        timeout: 5000,
        storage: { type: "memory" as const },
      };

      const adapter = StorageFactory.createStorageAdapter(config);
      expect(adapter).toBeInstanceOf(MemoryStorageAdapter);
    });

    test("should create filesystem storage adapter", () => {
      const config = {
        tempDir: TEST_TEMP_DIR,
        enableCaching: true,
        timeout: 5000,
        storage: { type: "filesystem" as const },
      };

      const adapter = StorageFactory.createStorageAdapter(config);
      expect(adapter).toBeInstanceOf(FilesystemStorageAdapter);
    });

    test("should create default filesystem adapter", () => {
      const config = {
        tempDir: TEST_TEMP_DIR,
        enableCaching: true,
        timeout: 5000,
      };

      const adapter = StorageFactory.createStorageAdapter(config);
      expect(adapter).toBeInstanceOf(FilesystemStorageAdapter);
    });
  });

  describe("FileHashCache", () => {
    let cache: FileHashCache;
    let storage: MemoryStorageAdapter;

    beforeEach(() => {
      storage = new MemoryStorageAdapter();
      cache = new FileHashCache(storage, { defaultTtl: 1000 });
    });

    test("should cache and retrieve data", async () => {
      const content = Buffer.from("test content");
      const data = { result: "processed content" };

      const hash = cache.generateFileHash(content);
      await cache.set(hash, data);

      const retrieved = await cache.get(hash);
      expect(retrieved).toEqual(data);
    });

    test("should handle cache misses", async () => {
      const result = await cache.get("non-existent-hash");
      expect(result).toBeNull();
    });

    test("should respect TTL", async () => {
      const shortTtlCache = new FileHashCache(storage, { defaultTtl: 1 }); // 1ms TTL
      const hash = "test-hash";
      const data = { test: "data" };

      await shortTtlCache.set(hash, data);

      // Wait for TTL to expire
      await new Promise((resolve) => setTimeout(resolve, 10));

      const retrieved = await shortTtlCache.get(hash);
      expect(retrieved).toBeNull();
    });

    test("should use getOrCompute pattern", async () => {
      const content = Buffer.from("test content");
      let computeCallCount = 0;

      const computeFn = async () => {
        computeCallCount++;
        return { computed: true, timestamp: Date.now() };
      };

      // First call should compute
      const result1 = await cache.getOrCompute(content, computeFn);
      expect(computeCallCount).toBe(1);
      expect(result1.computed).toBe(true);

      // Second call should use cache
      const result2 = await cache.getOrCompute(content, computeFn);
      expect(computeCallCount).toBe(1); // Should not increment
      expect(result2).toEqual(result1);
    });
  });

  describe("CleanupManager", () => {
    let cleanup: CleanupManager;

    beforeEach(() => {
      cleanup = new CleanupManager();
    });

    test("should register and cleanup temp directories", async () => {
      const tempDir = path.join(TEST_TEMP_DIR, "cleanup-test");
      cleanup.registerTempDirectory(tempDir);

      // Create some test files (would happen in real usage)
      const result = await cleanup.getCleanupStats({ dryRun: true });
      expect(result).toBeDefined();
      expect(result.errors).toBeInstanceOf(Array);
    });

    test("should schedule cleanup", () => {
      const intervalId = cleanup.scheduleCleanup(0.001); // Very short interval for testing
      expect(intervalId).toBeDefined();

      // Clean up the interval
      clearInterval(intervalId);
    });
  });
});
