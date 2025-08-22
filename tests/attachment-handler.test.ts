import { AttachmentHandler } from "../src/attachment-handler";
import { AttachmentInfo } from "../src/types";
import { TEST_TEMP_DIR } from "./setup";
import * as path from "path";

describe("AttachmentHandler", () => {
  let handler: AttachmentHandler;

  beforeEach(() => {
    handler = new AttachmentHandler({
      tempDir: path.join(TEST_TEMP_DIR, "attachments"),
      maxAttachmentSize: 1024 * 1024, // 1MB
      keepInMemoryThreshold: 1024, // 1KB
      blockedExtensions: [".exe", ".bat"],
    });
  });

  describe("processAttachment", () => {
    test("should process safe attachment", async () => {
      const attachment: AttachmentInfo = {
        filename: "test.txt",
        contentType: "text/plain",
        size: 100,
        content: Buffer.from("Test file content"),
      };

      const result = await handler.processAttachment(attachment);

      expect(result.attachment).toBe(attachment);
      expect(result.metadata.isProcessable).toBe(true);
      expect(result.metadata.securityFlags).toHaveLength(0);
      expect(result.hash).toBeDefined();
    });

    test("should block dangerous file extensions", async () => {
      const attachment: AttachmentInfo = {
        filename: "malware.exe",
        contentType: "application/x-msdownload",
        size: 1000,
        content: Buffer.from("fake executable content"),
      };

      const result = await handler.processAttachment(attachment);

      expect(result.metadata.isProcessable).toBe(false);
      expect(result.metadata.securityFlags).toContain(
        "blocked_extension: .exe",
      );
    });

    test("should flag large files", async () => {
      const attachment: AttachmentInfo = {
        filename: "large.txt",
        contentType: "text/plain",
        size: 2 * 1024 * 1024, // 2MB, larger than 1MB limit
        content: Buffer.alloc(2 * 1024 * 1024),
      };

      const result = await handler.processAttachment(attachment);

      expect(result.metadata.isProcessable).toBe(false);
      expect(
        result.metadata.securityFlags.some((flag) =>
          flag.includes("file_too_large"),
        ),
      ).toBe(true);
    });

    test("should detect suspicious MIME types", async () => {
      const attachment: AttachmentInfo = {
        filename: "suspicious.bin",
        contentType: "application/x-executable",
        size: 100,
        content: Buffer.from("suspicious content"),
      };

      const result = await handler.processAttachment(attachment);

      expect(
        result.metadata.securityFlags.some((flag) =>
          flag.includes("suspicious_mime_type"),
        ),
      ).toBe(true);
    });

    test("should keep small files in memory", async () => {
      const attachment: AttachmentInfo = {
        filename: "small.txt",
        contentType: "text/plain",
        size: 500, // Less than 1KB threshold
        content: Buffer.from("Small file content"),
      };

      const result = await handler.processAttachment(attachment);

      expect(result.inMemory).toBe(true);
      expect(result.localPath).toBeUndefined();
    });

    test("should store large files", async () => {
      const attachment: AttachmentInfo = {
        filename: "large.txt",
        contentType: "text/plain",
        size: 2000, // Larger than 1KB threshold
        content: Buffer.alloc(2000, "x"),
      };

      const result = await handler.processAttachment(attachment);

      expect(result.inMemory).toBe(false);
      expect(result.storageKey || result.localPath).toBeDefined();
    });
  });

  describe("processAttachments", () => {
    test("should process multiple attachments", async () => {
      const attachments: AttachmentInfo[] = [
        {
          filename: "doc1.txt",
          contentType: "text/plain",
          size: 100,
          content: Buffer.from("Document 1"),
        },
        {
          filename: "doc2.txt",
          contentType: "text/plain",
          size: 200,
          content: Buffer.from("Document 2"),
        },
      ];

      const results = await handler.processAttachments(attachments);

      expect(results).toHaveLength(2);
      expect(results[0].metadata.isProcessable).toBe(true);
      expect(results[1].metadata.isProcessable).toBe(true);
    });

    test("should handle processing errors gracefully", async () => {
      const attachments: AttachmentInfo[] = [
        {
          filename: "good.txt",
          contentType: "text/plain",
          size: 100,
          content: Buffer.from("Good file"),
        },
        {
          filename: undefined, // This might cause issues
          contentType: "unknown/type",
          size: 0,
          content: undefined,
        },
      ];

      const results = await handler.processAttachments(attachments);

      expect(results).toHaveLength(2);
      // First should succeed
      expect(results[0].metadata.isProcessable).toBe(true);
      // Second might have issues but shouldn't crash
      expect(results[1]).toBeDefined();
    });
  });

  describe("retrieveAttachment", () => {
    test("should retrieve in-memory attachment", async () => {
      const attachment: AttachmentInfo = {
        filename: "test.txt",
        contentType: "text/plain",
        size: 100,
        content: Buffer.from("Test content"),
      };

      const result = await handler.processAttachment(attachment);

      if (result.inMemory) {
        const retrieved = await handler.retrieveAttachment(result);
        expect(retrieved).toEqual(attachment.content);
      }
    });
  });

  describe("getAttachmentStats", () => {
    test("should return statistics", async () => {
      const attachments: AttachmentInfo[] = [
        {
          filename: "small.txt",
          contentType: "text/plain",
          size: 100,
          content: Buffer.from("Small"),
        },
        {
          filename: "malware.exe",
          contentType: "application/x-executable",
          size: 1000,
          content: Buffer.from("Blocked"),
        },
      ];

      const results = await handler.processAttachments(attachments);
      const stats = handler.getAttachmentStats(results);

      expect(stats.total).toBe(2);
      expect(stats.blocked).toBe(1);
      expect(stats.totalSize).toBe(1100);
    });
  });

  describe("filterProcessableAttachments", () => {
    test("should filter out blocked attachments", async () => {
      const attachments: AttachmentInfo[] = [
        {
          filename: "good.txt",
          contentType: "text/plain",
          size: 100,
          content: Buffer.from("Good"),
        },
        {
          filename: "bad.exe",
          contentType: "application/x-executable",
          size: 1000,
          content: Buffer.from("Bad"),
        },
      ];

      const results = await handler.processAttachments(attachments);
      const processable = handler.filterProcessableAttachments(results);

      expect(processable).toHaveLength(1);
      expect(processable[0].attachment.filename).toBe("good.txt");
    });
  });

  describe("getAttachmentsByType", () => {
    test("should filter attachments by content type", async () => {
      const attachments: AttachmentInfo[] = [
        {
          filename: "doc.txt",
          contentType: "text/plain",
          size: 100,
          content: Buffer.from("Text"),
        },
        {
          filename: "image.jpg",
          contentType: "image/jpeg",
          size: 1000,
          content: Buffer.from("Image"),
        },
      ];

      const results = await handler.processAttachments(attachments);
      const textFiles = handler.getAttachmentsByType(results, "text");

      expect(textFiles).toHaveLength(1);
      expect(textFiles[0].attachment.filename).toBe("doc.txt");
    });
  });
});
