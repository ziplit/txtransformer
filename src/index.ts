export { EmailTransformer } from "./EmailTransformer";
export * from "./types";
export * from "./schemas";
export { schemaValidator, ValidationResult } from "./validation";
export { schemaLoader, SchemaInfo } from "./schema-loader";

// Event system exports
export {
  TransformationEventEmitter,
  createTransformationContext,
  EventUtils,
} from "./events";
export type {
  TransformationEvents,
  TransformationContext,
  ProgressTracker,
} from "./events";

// Logger and error exports
export {
  createLogger,
  logger,
  TransformerError,
  EmailParsingError,
  AttachmentProcessingError,
  ValidationError,
  ConfigurationError,
  StorageError,
  logError,
  logPerformance,
  sanitizeForLogging,
} from "./logger";
export type { LoggerOptions } from "./logger";

// Configuration exports
export {
  ConfigManager,
  FileConfigSource,
  EnvConfigSource,
  createStandardConfigManager,
  loadConfig,
} from "./config";
export type { ConfigurationSource, ConfigValidationResult } from "./config";

// Service Discovery exports
export {
  ExtractorServiceDiscovery,
  createServiceDiscovery,
  autoDiscoverService,
} from "./service-discovery";
export type {
  ServiceEndpoint,
  ServiceDiscoveryOptions,
} from "./service-discovery";

// Storage exports
export {
  StorageFactory,
  MemoryStorageAdapter,
  FilesystemStorageAdapter,
} from "./storage";
export { FileHashCache, ProcessingCache } from "./storage/cache";
export { CleanupManager, cleanupManager } from "./storage/cleanup";

// Email parsing exports
export { EmailParser } from "./email-parser";
export type { EmailParsingOptions, EmailParsingResult } from "./email-parser";

// Attachment handling exports
export { AttachmentHandler } from "./attachment-handler";
export type {
  AttachmentHandlingOptions,
  AttachmentProcessingResult,
} from "./attachment-handler";
