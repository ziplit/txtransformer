import pino, { Logger } from "pino";

export interface LoggerOptions {
  /** Log level */
  level?: "trace" | "debug" | "info" | "warn" | "error" | "fatal";
  /** Enable pretty printing for development */
  pretty?: boolean;
  /** Logger name/component */
  name?: string;
  /** Custom transport options */
  transport?: any;
}

/**
 * Create a configured logger instance
 */
export function createLogger(options: LoggerOptions = {}): Logger {
  const {
    level = "info",
    pretty = process.env.NODE_ENV !== "production",
    name = "txtransformer",
    transport,
  } = options;

  const config: pino.LoggerOptions = {
    name,
    level,
  };

  // Add pretty printing transport for development
  if (pretty && !transport) {
    config.transport = {
      target: "pino-pretty",
      options: {
        colorize: true,
        translateTime: "SYS:standard",
        ignore: "pid,hostname",
      },
    };
  } else if (transport) {
    config.transport = transport;
  }

  return pino(config);
}

/**
 * Default logger instance
 */
export const logger = createLogger();

/**
 * Error classes for the library
 */
export class TransformerError extends Error {
  public readonly code: string;
  public readonly details?: any;

  constructor(
    message: string,
    code: string = "TRANSFORMER_ERROR",
    details?: any,
  ) {
    super(message);
    this.name = "TransformerError";
    this.code = code;
    this.details = details;
  }
}

export class EmailParsingError extends TransformerError {
  constructor(message: string, details?: any) {
    super(message, "EMAIL_PARSING_ERROR", details);
    this.name = "EmailParsingError";
  }
}

export class AttachmentProcessingError extends TransformerError {
  constructor(message: string, details?: any) {
    super(message, "ATTACHMENT_PROCESSING_ERROR", details);
    this.name = "AttachmentProcessingError";
  }
}

export class ValidationError extends TransformerError {
  constructor(message: string, details?: any) {
    super(message, "VALIDATION_ERROR", details);
    this.name = "ValidationError";
  }
}

export class ConfigurationError extends TransformerError {
  constructor(message: string, details?: any) {
    super(message, "CONFIGURATION_ERROR", details);
    this.name = "ConfigurationError";
  }
}

export class StorageError extends TransformerError {
  constructor(message: string, details?: any) {
    super(message, "STORAGE_ERROR", details);
    this.name = "StorageError";
  }
}

/**
 * Utility function to sanitize data for logging (remove sensitive information)
 */
export function sanitizeForLogging(data: any): any {
  if (typeof data !== "object" || data === null) {
    return data;
  }

  if (Buffer.isBuffer(data)) {
    return `[Buffer ${data.length} bytes]`;
  }

  const sanitized: any = Array.isArray(data) ? [] : {};
  const sensitiveFields = [
    "password",
    "apiKey",
    "token",
    "secret",
    "key",
    "content",
  ];

  for (const [key, value] of Object.entries(data)) {
    const keyLower = key.toLowerCase();

    if (sensitiveFields.some((field) => keyLower.includes(field))) {
      sanitized[key] = "[REDACTED]";
    } else if (typeof value === "object" && value !== null) {
      sanitized[key] = sanitizeForLogging(value);
    } else {
      sanitized[key] = value;
    }
  }

  return sanitized;
}

/**
 * Log performance metrics
 */
export function logPerformance(
  logger: Logger,
  operation: string,
  startTime: number,
  metadata?: any,
): void {
  const duration = Date.now() - startTime;
  logger.info(
    {
      operation,
      duration,
      ...sanitizeForLogging(metadata),
    },
    `Operation ${operation} completed in ${duration}ms`,
  );
}

/**
 * Log error with context
 */
export function logError(logger: Logger, error: Error, context?: any): void {
  const errorInfo = {
    error: {
      name: error.name,
      message: error.message,
      stack: error.stack,
      ...(error instanceof TransformerError
        ? {
            code: error.code,
            details: sanitizeForLogging(error.details),
          }
        : {}),
    },
    context: sanitizeForLogging(context),
  };

  logger.error(errorInfo, `Error: ${error.message}`);
}
