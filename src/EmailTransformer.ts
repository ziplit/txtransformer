import { TransformerConfig, ExtractionResult } from "./types";

export class EmailTransformer {
  private config: TransformerConfig;

  constructor(config: Partial<TransformerConfig> = {}) {
    this.config = {
      pythonExtractorUrl: config.pythonExtractorUrl || "http://localhost:8000",
      tempDir: config.tempDir || "./temp",
      enableCaching: config.enableCaching ?? true,
      timeout: config.timeout || 30000,
      ...config,
    };
  }

  /**
   * Transform email content to structured data
   */
  async transform(email: string | Buffer): Promise<ExtractionResult> {
    // TODO: Implement email transformation logic
    throw new Error("Not implemented yet");
  }

  /**
   * Transform email from file path
   */
  async transformFromFile(path: string): Promise<ExtractionResult> {
    // TODO: Implement file-based transformation
    throw new Error("Not implemented yet");
  }

  /**
   * Configure the transformer
   */
  configure(options: Partial<TransformerConfig>): void {
    this.config = { ...this.config, ...options };
  }

  /**
   * Get current configuration
   */
  getConfig(): TransformerConfig {
    return { ...this.config };
  }
}
