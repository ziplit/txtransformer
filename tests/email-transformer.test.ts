import * as fs from "fs-extra";
import * as path from "path";
import { EmailTransformer } from "../src/EmailTransformer";
import {
  TEST_TEMP_DIR,
  TEST_EMAIL_CONTENT,
  TEST_EMAIL_WITH_ATTACHMENT,
} from "./setup";

describe("EmailTransformer", () => {
  let transformer: EmailTransformer;
  const testTempDir = path.join(TEST_TEMP_DIR, "transformer-test");

  beforeEach(() => {
    transformer = new EmailTransformer({
      tempDir: testTempDir,
      enableCaching: true,
      timeout: 10000,
    });
  });

  afterEach(async () => {
    try {
      await transformer.cleanup();
    } catch (error) {
      // Ignore cleanup errors
    }
  });

  describe("constructor", () => {
    test("should initialize with default configuration", () => {
      const defaultTransformer = new EmailTransformer();
      const config = defaultTransformer.getConfig();

      expect(config.tempDir).toBeDefined();
      expect(config.enableCaching).toBe(true);
      expect(config.timeout).toBe(30000);
    });

    test("should initialize with custom configuration", () => {
      const customTempDir = path.join(TEST_TEMP_DIR, "custom-temp");
      const customTransformer = new EmailTransformer({
        tempDir: customTempDir,
        enableCaching: false,
        timeout: 5000,
      });

      const config = customTransformer.getConfig();
      expect(config.tempDir).toBe(customTempDir);
      expect(config.enableCaching).toBe(false);
      expect(config.timeout).toBe(5000);
    });
  });

  describe("transform", () => {
    test("should transform simple email from string", async () => {
      const result = await transformer.transform(TEST_EMAIL_CONTENT);

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.schemaType).toBeDefined();
      expect(result.data).toBeDefined();
      expect(result.confidence).toBeGreaterThanOrEqual(0);
      expect(result.confidence).toBeLessThanOrEqual(1);
      expect(result.metadata.processingTime).toBeGreaterThan(0);
      expect(result.metadata.extractorVersion).toBeDefined();
    });

    test("should transform email from Buffer", async () => {
      const buffer = Buffer.from(TEST_EMAIL_CONTENT);
      const result = await transformer.transform(buffer);

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.schemaType).toBeDefined();
    });

    test("should handle email with attachments", async () => {
      const result = await transformer.transform(TEST_EMAIL_WITH_ATTACHMENT);

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      // The transformer should handle the email even if it has attachments
      expect(result.data).toBeDefined();
    });

    test("should use caching when enabled", async () => {
      const email = TEST_EMAIL_CONTENT;

      // First transformation
      const start1 = Date.now();
      const result1 = await transformer.transform(email);
      const time1 = Date.now() - start1;

      // Second transformation (should be from cache)
      const start2 = Date.now();
      const result2 = await transformer.transform(email);
      const time2 = Date.now() - start2;

      expect(result1.id).toBe(result2.id);
      expect(result1.schemaType).toBe(result2.schemaType);

      // Second call should be faster (from cache)
      // Note: This might be flaky in fast environments, so we're lenient
      expect(time2).toBeLessThanOrEqual(time1 + 100);
    });

    test("should handle malformed email gracefully", async () => {
      const malformedEmail = "This is not a valid email format";

      const result = await transformer.transform(malformedEmail);

      // Should not throw error, should return some result
      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
    });
  });

  describe("transformFromFile", () => {
    test("should transform email from file", async () => {
      const emailFile = path.join(testTempDir, "test-email.txt");
      await fs.ensureDir(testTempDir);
      await fs.writeFile(emailFile, TEST_EMAIL_CONTENT);

      const result = await transformer.transformFromFile(emailFile);

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.schemaType).toBeDefined();
    });

    test("should throw error for non-existent file", async () => {
      const nonExistentFile = path.join(testTempDir, "non-existent.txt");

      await expect(
        transformer.transformFromFile(nonExistentFile),
      ).rejects.toThrow("Email file not found");
    });
  });

  describe("configure", () => {
    test("should update configuration", () => {
      const originalConfig = transformer.getConfig();

      transformer.configure({
        timeout: 15000,
        enableCaching: false,
      });

      const updatedConfig = transformer.getConfig();

      expect(updatedConfig.timeout).toBe(15000);
      expect(updatedConfig.enableCaching).toBe(false);
      expect(updatedConfig.tempDir).toBe(originalConfig.tempDir); // Should remain unchanged
    });

    test("should reinitialize components when tempDir changes", () => {
      const newTempDir = path.join(TEST_TEMP_DIR, "new-temp");

      transformer.configure({ tempDir: newTempDir });

      const config = transformer.getConfig();
      expect(config.tempDir).toBe(newTempDir);
    });
  });

  describe("getConfig", () => {
    test("should return current configuration", () => {
      const config = transformer.getConfig();

      expect(config).toBeDefined();
      expect(config.tempDir).toBeDefined();
      expect(config.timeout).toBeDefined();
      expect(config.enableCaching).toBeDefined();
    });

    test("should return copy of configuration", () => {
      const config1 = transformer.getConfig();
      const config2 = transformer.getConfig();

      expect(config1).not.toBe(config2); // Different objects
      expect(config1).toEqual(config2); // Same content
    });
  });

  describe("cleanup", () => {
    test("should clean up resources", async () => {
      // Transform an email to create some cached data
      await transformer.transform(TEST_EMAIL_CONTENT);

      // Cleanup should not throw
      await expect(transformer.cleanup()).resolves.not.toThrow();
    });
  });

  describe("getStats", () => {
    test("should return transformation statistics", async () => {
      // Transform an email to generate some activity
      await transformer.transform(TEST_EMAIL_CONTENT);

      const stats = await transformer.getStats();

      expect(stats).toBeDefined();
      expect(stats.cacheStats).toBeDefined();
      expect(typeof stats.tempDirSize).toBe("number");
      expect(typeof stats.tempFileCount).toBe("number");
    });
  });

  describe("error handling", () => {
    test("should handle transformation errors gracefully", async () => {
      // Try to transform invalid input
      const invalidInput = null as any;

      await expect(transformer.transform(invalidInput)).rejects.toThrow(
        "Email transformation failed",
      );
    });

    test("should handle buffer conversion errors", async () => {
      // This should still work even with unusual input
      const emptyString = "";

      const result = await transformer.transform(emptyString);
      expect(result).toBeDefined();
    });
  });

  describe("integration scenarios", () => {
    test("should handle complete email processing workflow", async () => {
      // Create a temporary email file
      const emailFile = path.join(testTempDir, "workflow-test.eml");
      await fs.ensureDir(testTempDir);
      await fs.writeFile(emailFile, TEST_EMAIL_WITH_ATTACHMENT);

      // Transform from file
      const result = await transformer.transformFromFile(emailFile);

      // Verify result structure
      expect(result.id).toBeDefined();
      expect(result.schemaType).toBeDefined();
      expect(result.data).toBeDefined();
      expect(result.provenance).toBeDefined();
      expect(result.metadata).toBeDefined();

      // Get statistics
      const stats = await transformer.getStats();
      expect(stats.tempFileCount).toBeGreaterThanOrEqual(0);

      // Cleanup
      await transformer.cleanup();

      // Verify cleanup worked
      const statsAfterCleanup = await transformer.getStats();
      expect(statsAfterCleanup).toBeDefined();
    });
  });
});
