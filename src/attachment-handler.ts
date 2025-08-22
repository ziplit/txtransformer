import * as fs from "fs-extra";
import * as path from "path";
import * as crypto from "crypto";
import { AttachmentInfo, StorageAdapter } from "./types";
import { StorageFactory } from "./storage";

export interface AttachmentHandlingOptions {
  /** Base directory for temporary attachment storage */
  tempDir: string;
  /** Maximum attachment size to process (bytes) */
  maxAttachmentSize: number;
  /** Storage adapter to use */
  storageAdapter?: StorageAdapter;
  /** Keep attachments in memory for small files */
  keepInMemoryThreshold: number;
  /** Allowed file extensions */
  allowedExtensions?: string[];
  /** Blocked file extensions for security */
  blockedExtensions: string[];
}

export interface AttachmentProcessingResult {
  /** Original attachment info */
  attachment: AttachmentInfo;
  /** Local file path where attachment is stored */
  localPath?: string;
  /** Storage key if stored via adapter */
  storageKey?: string;
  /** Whether attachment content is kept in memory */
  inMemory: boolean;
  /** File hash for caching/deduplication */
  hash: string;
  /** Processing metadata */
  metadata: {
    originalSize: number;
    mimeType: string;
    isProcessable: boolean;
    securityFlags: string[];
  };
}

/**
 * Handles email attachments with temporary storage and security checks
 */
export class AttachmentHandler {
  private options: Required<
    Omit<AttachmentHandlingOptions, "storageAdapter" | "allowedExtensions">
  > &
    Pick<AttachmentHandlingOptions, "storageAdapter" | "allowedExtensions">;
  private storage: StorageAdapter;

  constructor(options: AttachmentHandlingOptions) {
    this.options = {
      ...options,
      maxAttachmentSize: options.maxAttachmentSize ?? 50 * 1024 * 1024, // 50MB
      keepInMemoryThreshold: options.keepInMemoryThreshold ?? 1024 * 1024, // 1MB
      blockedExtensions: options.blockedExtensions ?? [
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".pif",
        ".scr",
        ".vbs",
        ".js",
      ],
    };

    // Initialize storage adapter
    this.storage =
      this.options.storageAdapter ||
      StorageFactory.createStorageAdapter({
        tempDir: this.options.tempDir,
        enableCaching: true,
        timeout: 30000,
      });
  }

  /**
   * Process multiple attachments
   */
  async processAttachments(
    attachments: AttachmentInfo[],
  ): Promise<AttachmentProcessingResult[]> {
    const results: AttachmentProcessingResult[] = [];

    for (const attachment of attachments) {
      try {
        const result = await this.processAttachment(attachment);
        results.push(result);
      } catch (error) {
        // Create error result for failed attachments
        const errorResult: AttachmentProcessingResult = {
          attachment,
          inMemory: false,
          hash: "",
          metadata: {
            originalSize: attachment.size,
            mimeType: attachment.contentType,
            isProcessable: false,
            securityFlags: [
              `processing_error: ${error instanceof Error ? error.message : "Unknown error"}`,
            ],
          },
        };
        results.push(errorResult);
      }
    }

    return results;
  }

  /**
   * Process a single attachment
   */
  async processAttachment(
    attachment: AttachmentInfo,
  ): Promise<AttachmentProcessingResult> {
    // Perform security checks
    const securityFlags = this.performSecurityChecks(attachment);
    const isProcessable = securityFlags.length === 0;

    // Generate hash for the attachment
    let hash = "";
    let localPath: string | undefined;
    let storageKey: string | undefined;
    let inMemory = false;

    if (attachment.content && isProcessable) {
      hash = this.generateHash(attachment.content);

      // Determine storage strategy
      if (attachment.size <= this.options.keepInMemoryThreshold) {
        // Keep small attachments in memory
        inMemory = true;
      } else {
        // Store larger attachments
        const result = await this.storeAttachment(attachment, hash);
        localPath = result.localPath;
        storageKey = result.storageKey;
      }
    }

    return {
      attachment,
      localPath,
      storageKey,
      inMemory,
      hash,
      metadata: {
        originalSize: attachment.size,
        mimeType: attachment.contentType,
        isProcessable,
        securityFlags,
      },
    };
  }

  /**
   * Store attachment using the configured strategy
   */
  private async storeAttachment(
    attachment: AttachmentInfo,
    hash: string,
  ): Promise<{ localPath?: string; storageKey?: string }> {
    if (!attachment.content) {
      throw new Error("Attachment content is required for storage");
    }

    // Generate storage key
    const extension = this.getFileExtension(attachment.filename || "");
    const storageKey = `${hash}${extension}`;

    try {
      // Store via storage adapter
      await this.storage.store(storageKey, attachment.content);

      // For filesystem storage, we might also get a local path
      const localPath = await this.getLocalPath(storageKey);

      return { localPath, storageKey };
    } catch (error) {
      throw new Error(
        `Failed to store attachment: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  /**
   * Retrieve attachment content
   */
  async retrieveAttachment(
    result: AttachmentProcessingResult,
  ): Promise<Buffer> {
    if (result.inMemory && result.attachment.content) {
      return result.attachment.content;
    }

    if (result.storageKey) {
      return await this.storage.retrieve(result.storageKey);
    }

    if (result.localPath) {
      return await fs.readFile(result.localPath);
    }

    throw new Error("No valid storage location found for attachment");
  }

  /**
   * Clean up temporary attachment files
   */
  async cleanup(results: AttachmentProcessingResult[]): Promise<void> {
    const cleanupPromises = results.map(async (result) => {
      try {
        if (result.storageKey) {
          await this.storage.delete(result.storageKey);
        }
        if (result.localPath && (await fs.pathExists(result.localPath))) {
          await fs.unlink(result.localPath);
        }
      } catch (error) {
        // Ignore cleanup errors
      }
    });

    await Promise.all(cleanupPromises);
  }

  /**
   * Perform security checks on attachment
   */
  private performSecurityChecks(attachment: AttachmentInfo): string[] {
    const flags: string[] = [];

    // Check file size
    if (attachment.size > this.options.maxAttachmentSize) {
      flags.push(
        `file_too_large: ${attachment.size} > ${this.options.maxAttachmentSize}`,
      );
    }

    // Check file extension
    if (attachment.filename) {
      const extension = this.getFileExtension(
        attachment.filename,
      ).toLowerCase();

      if (this.options.blockedExtensions.includes(extension)) {
        flags.push(`blocked_extension: ${extension}`);
      }

      if (
        this.options.allowedExtensions &&
        !this.options.allowedExtensions.includes(extension)
      ) {
        flags.push(`extension_not_allowed: ${extension}`);
      }
    }

    // Check MIME type
    if (this.isSuspiciousMimeType(attachment.contentType)) {
      flags.push(`suspicious_mime_type: ${attachment.contentType}`);
    }

    // Check for embedded executables (basic check)
    if (
      attachment.content &&
      this.containsExecutableSignatures(attachment.content)
    ) {
      flags.push("possible_executable_content");
    }

    return flags;
  }

  /**
   * Check if MIME type is suspicious
   */
  private isSuspiciousMimeType(mimeType: string): boolean {
    const suspiciousTypes = [
      "application/x-msdownload",
      "application/x-executable",
      "application/octet-stream", // Too generic, could be anything
      "application/x-dosexec",
    ];

    return suspiciousTypes.some((type) => mimeType.includes(type));
  }

  /**
   * Basic check for executable signatures in content
   */
  private containsExecutableSignatures(content: Buffer): boolean {
    if (content.length < 4) return false;

    // Check for common executable signatures
    const signatures = [
      Buffer.from("MZ"), // DOS/Windows executable
      Buffer.from("\x7fELF"), // Linux ELF
      Buffer.from("\xfe\xed\xfa"), // Mach-O (macOS)
    ];

    return signatures.some((sig) =>
      content.subarray(0, sig.length).equals(sig),
    );
  }

  /**
   * Generate hash for attachment content
   */
  private generateHash(content: Buffer): string {
    return crypto.createHash("sha256").update(content).digest("hex");
  }

  /**
   * Extract file extension from filename
   */
  private getFileExtension(filename: string): string {
    const ext = path.extname(filename);
    return ext || "";
  }

  /**
   * Get local file path for stored attachment (filesystem adapter specific)
   */
  private async getLocalPath(storageKey: string): Promise<string | undefined> {
    // This is a simplified approach - in practice, you might need to
    // check the storage adapter type and get the actual local path
    const tempPath = path.join(this.options.tempDir, storageKey);

    if (await fs.pathExists(tempPath)) {
      return tempPath;
    }

    return undefined;
  }

  /**
   * Get attachment statistics
   */
  getAttachmentStats(results: AttachmentProcessingResult[]): {
    total: number;
    inMemory: number;
    stored: number;
    blocked: number;
    totalSize: number;
  } {
    return results.reduce(
      (stats, result) => {
        stats.total++;

        if (result.inMemory) stats.inMemory++;
        if (result.storageKey || result.localPath) stats.stored++;
        if (!result.metadata.isProcessable) stats.blocked++;

        stats.totalSize += result.metadata.originalSize;

        return stats;
      },
      {
        total: 0,
        inMemory: 0,
        stored: 0,
        blocked: 0,
        totalSize: 0,
      },
    );
  }

  /**
   * Filter attachments by type for processing
   */
  filterProcessableAttachments(
    results: AttachmentProcessingResult[],
  ): AttachmentProcessingResult[] {
    return results.filter((result) => result.metadata.isProcessable);
  }

  /**
   * Get attachments by content type
   */
  getAttachmentsByType(
    results: AttachmentProcessingResult[],
    mimeType: string,
  ): AttachmentProcessingResult[] {
    return results.filter((result) =>
      result.attachment.contentType
        .toLowerCase()
        .includes(mimeType.toLowerCase()),
    );
  }
}
