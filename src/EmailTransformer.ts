import * as fs from "fs-extra";
import * as path from "path";
import { TransformerConfig, ExtractionResult, EmailCanonical } from "./types";
import { EmailParser, EmailParsingOptions } from "./email-parser";
import {
  AttachmentHandler,
  AttachmentProcessingResult,
} from "./attachment-handler";
import { SchemaValidator } from "./validation";
import { StorageFactory } from "./storage";
import { ProcessingCache } from "./storage/cache";
import { cleanupManager } from "./storage/cleanup";
import {
  createLogger,
  logger as defaultLogger,
  TransformerError,
  EmailParsingError,
  AttachmentProcessingError,
  ValidationError,
  StorageError,
  logError,
  logPerformance,
  LoggerOptions,
} from "./logger";
import {
  TransformationEventEmitter,
  createTransformationContext,
  TransformationContext,
} from "./events";
import { Logger } from "pino";

export interface TransformationResult {
  /** Extraction result */
  result: ExtractionResult;
  /** Processed attachments */
  attachments: AttachmentProcessingResult[];
  /** Processing metadata */
  metadata: {
    processingTime: number;
    cacheHit: boolean;
    attachmentCount: number;
  };
}

export class EmailTransformer extends TransformationEventEmitter {
  private config: TransformerConfig;
  private emailParser: EmailParser;
  private attachmentHandler: AttachmentHandler;
  private schemaValidator: SchemaValidator;
  private processingCache: ProcessingCache;
  private logger: Logger;

  constructor(
    config: Partial<TransformerConfig> = {},
    loggerOptions?: LoggerOptions,
  ) {
    super();

    // Set default configuration
    this.config = {
      pythonExtractorUrl: config.pythonExtractorUrl || "http://localhost:8000",
      tempDir: config.tempDir || "./temp",
      enableCaching: config.enableCaching ?? true,
      timeout: config.timeout || 30000,
      ...config,
    };

    // Initialize logger
    this.logger = loggerOptions ? createLogger(loggerOptions) : defaultLogger;

    // Initialize components
    this.emailParser = new EmailParser({
      keepAttachments: true,
      maxAttachmentSize: 50 * 1024 * 1024,
    });

    this.attachmentHandler = new AttachmentHandler({
      tempDir: this.config.tempDir,
      maxAttachmentSize: 50 * 1024 * 1024,
      keepInMemoryThreshold: 1024 * 1024,
      blockedExtensions: [
        ".exe",
        ".bat",
        ".cmd",
        ".com",
        ".pif",
        ".scr",
        ".vbs",
        ".js",
      ],
    });

    this.schemaValidator = new SchemaValidator();

    // Initialize storage and cache
    const storage = StorageFactory.createStorageAdapter(this.config);
    this.processingCache = new ProcessingCache(storage);

    // Register cleanup
    cleanupManager.registerTempDirectory(this.config.tempDir);

    this.ensureTempDirectory();
  }

  /**
   * Transform email content to structured data
   */
  async transform(email: string | Buffer): Promise<ExtractionResult> {
    // Validate input
    if (email === null || email === undefined) {
      throw new TransformerError(
        "Email content cannot be null or undefined",
        "INVALID_INPUT",
      );
    }

    // Create transformation context
    const context = createTransformationContext(
      this.generateEmailHash(email),
      this,
    );

    this.logger.info(
      { transformationId: context.id },
      "Starting email transformation",
    );

    this.emit("transformation:started", {
      id: context.id,
      email: {} as EmailCanonical, // Will be populated after parsing
    });

    try {
      // Parse email
      context.progress.nextStage("parsing");
      this.logger.debug({ transformationId: context.id }, "Parsing email");

      const parseResult = await this.emailParser.parseEmail(email);
      const canonicalEmail = parseResult.email;

      this.emit("email:parsed", {
        id: context.id,
        email: canonicalEmail,
        metadata: parseResult.metadata,
      });

      // Update transformation started event with actual email data
      this.emit("transformation:started", {
        id: context.id,
        email: canonicalEmail,
      });

      // Process attachments
      context.progress.nextStage("attachment-processing");
      this.logger.debug(
        {
          transformationId: context.id,
          attachmentCount: canonicalEmail.attachments.length,
        },
        "Processing attachments",
      );

      this.emit("attachments:processing-started", {
        id: context.id,
        count: canonicalEmail.attachments.length,
      });

      const attachmentResults = await this.attachmentHandler.processAttachments(
        canonicalEmail.attachments,
      );

      const attachmentStats =
        this.attachmentHandler.getAttachmentStats(attachmentResults);
      this.emit("attachments:processed", {
        id: context.id,
        results: attachmentResults,
        stats: attachmentStats,
      });

      // Log blocked attachments
      attachmentResults
        .filter((result) => !result.metadata.isProcessable)
        .forEach((result) => {
          this.emit("attachment:blocked", {
            id: context.id,
            attachment: result.attachment,
            reason: result.metadata.securityFlags.join(", "),
          });
        });

      // Check cache for existing results
      context.progress.nextStage("caching");
      let extractionResult: ExtractionResult;

      if (this.config.enableCaching) {
        const cached = await this.processingCache.getCachedTextExtraction(
          Buffer.isBuffer(email) ? email : Buffer.from(email),
        );

        if (cached) {
          this.emit("cache:hit", { id: context.id, key: "text-extraction" });
          this.logger.debug(
            { transformationId: context.id },
            "Cache hit for transformation",
          );

          extractionResult = JSON.parse(cached);
          extractionResult.metadata.processingTime =
            Date.now() - context.startTime;

          context.progress.complete();
          this.emit("transformation:completed", {
            id: context.id,
            result: extractionResult,
            duration: extractionResult.metadata.processingTime,
          });

          logPerformance(
            this.logger,
            "email-transformation",
            context.startTime,
            {
              cached: true,
              attachmentCount: canonicalEmail.attachments.length,
            },
          );

          return extractionResult;
        } else {
          this.emit("cache:miss", { id: context.id, key: "text-extraction" });
        }
      }

      // Perform extraction
      context.progress.nextStage("extraction");
      this.logger.debug(
        { transformationId: context.id },
        "Performing extraction",
      );

      extractionResult = await this.performExtraction(
        canonicalEmail,
        attachmentResults,
        context,
      );

      // Cache result if enabled
      if (this.config.enableCaching) {
        await this.processingCache.cacheTextExtraction(
          Buffer.isBuffer(email) ? email : Buffer.from(email),
          JSON.stringify(extractionResult),
        );
        this.emit("cache:stored", { id: context.id, key: "text-extraction" });
      }

      // Update processing time
      extractionResult.metadata.processingTime = Date.now() - context.startTime;

      context.progress.complete();
      this.emit("transformation:completed", {
        id: context.id,
        result: extractionResult,
        duration: extractionResult.metadata.processingTime,
      });

      logPerformance(this.logger, "email-transformation", context.startTime, {
        schemaType: extractionResult.schemaType,
        confidence: extractionResult.confidence,
        attachmentCount: canonicalEmail.attachments.length,
      });

      return extractionResult;
    } catch (error) {
      const transformationError =
        error instanceof TransformerError
          ? error
          : new TransformerError(
              `Email transformation failed: ${error instanceof Error ? error.message : "Unknown error"}`,
              "TRANSFORMATION_ERROR",
              { originalError: error },
            );

      logError(this.logger, transformationError, {
        transformationId: context.id,
      });

      this.emit("transformation:failed", {
        id: context.id,
        error: transformationError,
        duration: Date.now() - context.startTime,
      });

      throw transformationError;
    }
  }

  /**
   * Transform email from file path
   */
  async transformFromFile(filePath: string): Promise<ExtractionResult> {
    if (!(await fs.pathExists(filePath))) {
      throw new Error(`Email file not found: ${filePath}`);
    }

    const emailData = await fs.readFile(filePath);
    return this.transform(emailData);
  }

  /**
   * Configure the transformer
   */
  configure(options: Partial<TransformerConfig>): void {
    this.config = { ...this.config, ...options };

    // Reinitialize components if necessary
    if (options.tempDir) {
      this.attachmentHandler = new AttachmentHandler({
        tempDir: options.tempDir,
        maxAttachmentSize: 50 * 1024 * 1024,
        keepInMemoryThreshold: 1024 * 1024,
        blockedExtensions: [
          ".exe",
          ".bat",
          ".cmd",
          ".com",
          ".pif",
          ".scr",
          ".vbs",
          ".js",
        ],
      });
      this.ensureTempDirectory();
    }
  }

  /**
   * Get current configuration
   */
  getConfig(): TransformerConfig {
    return { ...this.config };
  }

  /**
   * Clean up temporary files and cache
   */
  async cleanup(): Promise<void> {
    await cleanupManager.cleanup();
    await this.processingCache.clear();
  }

  /**
   * Get transformation statistics
   */
  async getStats(): Promise<{
    cacheStats: any;
    tempDirSize: number;
    tempFileCount: number;
  }> {
    const cacheStats = await this.processingCache.cleanup();
    const tempDirInfo = await this.getTempDirectoryInfo();

    return {
      cacheStats,
      tempDirSize: tempDirInfo.size,
      tempFileCount: tempDirInfo.fileCount,
    };
  }

  /**
   * Perform the actual extraction (placeholder implementation)
   */
  private async performExtraction(
    email: EmailCanonical,
    attachments: AttachmentProcessingResult[],
    context?: TransformationContext,
  ): Promise<ExtractionResult> {
    // This is a placeholder implementation
    // In a full implementation, this would:
    // 1. Call the Python extractor service
    // 2. Apply schema validation
    // 3. Perform confidence scoring
    // 4. Generate provenance information

    // Emit schema validation events
    if (context) {
      this.emit("schema:validation-started", {
        id: context.id,
        schemaType: "generic_message",
      });
    }

    // For now, return a basic result with generic message classification
    const validationResult = this.schemaValidator.validateAgainstDomainSchemas({
      messageId: email.id,
      subject: email.subject,
      from: {
        email: email.from,
      },
      classification: {
        category: "other",
        intent: "informational",
        confidence: 0.5,
      },
      bodySummary: email.text.substring(0, 200),
    });

    if (context) {
      this.emit("schema:validation-completed", {
        id: context.id,
        schemaType: validationResult.detectedDomain || "generic_message",
        valid: validationResult.valid,
        confidence: 0.5,
      });
    }

    // Create basic generic message data
    const genericData = {
      messageId: email.id,
      subject: email.subject,
      from: {
        email: email.from,
      },
      classification: {
        category: "other" as const,
        intent: "informational" as const,
        confidence: 0.5,
      },
      bodySummary: email.text.substring(0, 200),
    };

    return {
      id: email.id,
      schemaType: validationResult.detectedDomain || "generic_message",
      data: genericData,
      confidence: 0.5,
      provenance: {
        fieldSources: {},
        extractionMethods: ["schema_validation"],
        methodConfidence: {
          schema_validation: 0.5,
        },
      },
      metadata: {
        processingTime: 0, // Will be set by caller
        extractorVersion: "0.1.0",
        timestamp: new Date().toISOString(),
      },
    };
  }

  /**
   * Generate hash for email content
   */
  private generateEmailHash(email: string | Buffer): string {
    const crypto = require("crypto");
    const content = Buffer.isBuffer(email) ? email : Buffer.from(email);
    return crypto.createHash("sha256").update(content).digest("hex");
  }

  /**
   * Ensure temporary directory exists
   */
  private async ensureTempDirectory(): Promise<void> {
    await fs.ensureDir(this.config.tempDir);
  }

  /**
   * Get temporary directory information
   */
  private async getTempDirectoryInfo(): Promise<{
    size: number;
    fileCount: number;
  }> {
    if (!(await fs.pathExists(this.config.tempDir))) {
      return { size: 0, fileCount: 0 };
    }

    let totalSize = 0;
    let fileCount = 0;

    const walkDirectory = async (dir: string) => {
      const items = await fs.readdir(dir, { withFileTypes: true });

      for (const item of items) {
        const itemPath = path.join(dir, item.name);

        if (item.isDirectory()) {
          await walkDirectory(itemPath);
        } else {
          const stats = await fs.stat(itemPath);
          totalSize += stats.size;
          fileCount++;
        }
      }
    };

    await walkDirectory(this.config.tempDir);

    return { size: totalSize, fileCount };
  }
}
