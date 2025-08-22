import { EventEmitter } from "events";
import { ExtractionResult, EmailCanonical, AttachmentInfo } from "./types";
import { AttachmentProcessingResult } from "./attachment-handler";

export interface TransformationEvents {
  // Transformation lifecycle events
  "transformation:started": (data: {
    id: string;
    email: EmailCanonical;
  }) => void;
  "transformation:completed": (data: {
    id: string;
    result: ExtractionResult;
    duration: number;
  }) => void;
  "transformation:failed": (data: {
    id: string;
    error: Error;
    duration: number;
  }) => void;

  // Email parsing events
  "email:parsed": (data: {
    id: string;
    email: EmailCanonical;
    metadata: any;
  }) => void;
  "email:parsing-failed": (data: { id: string; error: Error }) => void;

  // Attachment processing events
  "attachments:processing-started": (data: {
    id: string;
    count: number;
  }) => void;
  "attachments:processed": (data: {
    id: string;
    results: AttachmentProcessingResult[];
    stats: any;
  }) => void;
  "attachment:blocked": (data: {
    id: string;
    attachment: AttachmentInfo;
    reason: string;
  }) => void;

  // Cache events
  "cache:hit": (data: { id: string; key: string }) => void;
  "cache:miss": (data: { id: string; key: string }) => void;
  "cache:stored": (data: { id: string; key: string }) => void;

  // Schema validation events
  "schema:validation-started": (data: {
    id: string;
    schemaType: string;
  }) => void;
  "schema:validation-completed": (data: {
    id: string;
    schemaType: string;
    valid: boolean;
    confidence: number;
  }) => void;

  // Progress events
  progress: (data: {
    id: string;
    stage: string;
    progress: number;
    total: number;
  }) => void;

  // Warning events
  warning: (data: { id: string; message: string; details?: any }) => void;
}

export type TransformationEventName = keyof TransformationEvents;

/**
 * Type-safe event emitter for transformation events
 */
export class TransformationEventEmitter extends EventEmitter {
  emit<K extends TransformationEventName>(
    eventName: K,
    data: Parameters<TransformationEvents[K]>[0],
  ): boolean {
    return super.emit(eventName, data);
  }

  on<K extends TransformationEventName>(
    eventName: K,
    listener: TransformationEvents[K],
  ): this {
    return super.on(eventName, listener);
  }

  once<K extends TransformationEventName>(
    eventName: K,
    listener: TransformationEvents[K],
  ): this {
    return super.once(eventName, listener);
  }

  off<K extends TransformationEventName>(
    eventName: K,
    listener: TransformationEvents[K],
  ): this {
    return super.off(eventName, listener);
  }

  removeListener<K extends TransformationEventName>(
    eventName: K,
    listener: TransformationEvents[K],
  ): this {
    return super.removeListener(eventName, listener);
  }
}

/**
 * Progress tracker for transformations
 */
export class ProgressTracker {
  private emitter: TransformationEventEmitter;
  private id: string;
  private stages: string[] = [];
  private currentStage: number = 0;

  constructor(
    emitter: TransformationEventEmitter,
    id: string,
    stages: string[],
  ) {
    this.emitter = emitter;
    this.id = id;
    this.stages = stages;
  }

  /**
   * Move to the next stage
   */
  nextStage(stageName?: string): void {
    if (stageName && !this.stages.includes(stageName)) {
      this.stages.push(stageName);
    }

    if (stageName) {
      const stageIndex = this.stages.indexOf(stageName);
      if (stageIndex >= 0) {
        this.currentStage = stageIndex;
      }
    } else {
      this.currentStage++;
    }

    this.emitProgress();
  }

  /**
   * Set progress within current stage
   */
  setProgress(progress: number): void {
    const baseProgress = this.currentStage * (100 / this.stages.length);
    const stageProgress = (progress * (100 / this.stages.length)) / 100;
    const totalProgress = Math.min(100, baseProgress + stageProgress);

    this.emitter.emit("progress", {
      id: this.id,
      stage: this.stages[this.currentStage] || "unknown",
      progress: Math.round(totalProgress),
      total: 100,
    });
  }

  /**
   * Complete all stages
   */
  complete(): void {
    this.emitter.emit("progress", {
      id: this.id,
      stage: "completed",
      progress: 100,
      total: 100,
    });
  }

  private emitProgress(): void {
    const progress = Math.round((this.currentStage / this.stages.length) * 100);

    this.emitter.emit("progress", {
      id: this.id,
      stage: this.stages[this.currentStage] || "unknown",
      progress,
      total: 100,
    });
  }
}

/**
 * Event-driven transformation context
 */
export interface TransformationContext {
  /** Unique transformation ID */
  id: string;
  /** Event emitter for this transformation */
  emitter: TransformationEventEmitter;
  /** Progress tracker */
  progress: ProgressTracker;
  /** Start time for performance tracking */
  startTime: number;
  /** Metadata for the transformation */
  metadata: Record<string, any>;
}

/**
 * Create a new transformation context
 */
export function createTransformationContext(
  id: string,
  emitter: TransformationEventEmitter,
  stages: string[] = [
    "parsing",
    "attachment-processing",
    "extraction",
    "validation",
    "caching",
  ],
): TransformationContext {
  return {
    id,
    emitter,
    progress: new ProgressTracker(emitter, id, stages),
    startTime: Date.now(),
    metadata: {},
  };
}

/**
 * Utility functions for common event patterns
 */
export class EventUtils {
  /**
   * Create a Promise that resolves when a specific event is emitted
   */
  static waitForEvent<K extends TransformationEventName>(
    emitter: TransformationEventEmitter,
    eventName: K,
    timeout?: number,
  ): Promise<Parameters<TransformationEvents[K]>[0]> {
    return new Promise((resolve, reject) => {
      let timeoutId: NodeJS.Timeout | undefined;

      const cleanup = () => {
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
      };

      const listener = (data: Parameters<TransformationEvents[K]>[0]) => {
        cleanup();
        resolve(data);
      };

      emitter.once(eventName, listener);

      if (timeout) {
        timeoutId = setTimeout(() => {
          emitter.off(eventName, listener);
          reject(new Error(`Event ${eventName} timeout after ${timeout}ms`));
        }, timeout);
      }
    });
  }

  /**
   * Create an async iterator for events
   */
  static async *eventIterator<K extends TransformationEventName>(
    emitter: TransformationEventEmitter,
    eventName: K,
  ): AsyncIterableIterator<Parameters<TransformationEvents[K]>[0]> {
    const queue: Parameters<TransformationEvents[K]>[0][] = [];
    let resolve: ((value: any) => void) | null = null;
    let finished = false;

    const listener = (data: Parameters<TransformationEvents[K]>[0]) => {
      if (resolve) {
        resolve({ value: data, done: false });
        resolve = null;
      } else {
        queue.push(data);
      }
    };

    emitter.on(eventName, listener);

    try {
      while (!finished) {
        if (queue.length > 0) {
          yield queue.shift()!;
        } else {
          const result = await new Promise<{
            value: Parameters<TransformationEvents[K]>[0];
            done: boolean;
          }>((res) => {
            resolve = res;
          });

          if (!result.done) {
            yield result.value;
          }
        }
      }
    } finally {
      emitter.off(eventName, listener);
    }
  }

  /**
   * Batch events over a time window
   */
  static batchEvents<K extends TransformationEventName>(
    emitter: TransformationEventEmitter,
    eventName: K,
    windowMs: number,
    callback: (events: Parameters<TransformationEvents[K]>[0][]) => void,
  ): () => void {
    const batches: Parameters<TransformationEvents[K]>[0][] = [];
    let timeoutId: NodeJS.Timeout | null = null;

    const flush = () => {
      if (batches.length > 0) {
        callback([...batches]);
        batches.length = 0;
      }
      timeoutId = null;
    };

    const listener = (data: Parameters<TransformationEvents[K]>[0]) => {
      batches.push(data);

      if (!timeoutId) {
        timeoutId = setTimeout(flush, windowMs);
      }
    };

    emitter.on(eventName, listener);

    return () => {
      emitter.off(eventName, listener);
      if (timeoutId) {
        clearTimeout(timeoutId);
        flush();
      }
    };
  }
}
