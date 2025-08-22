import * as fs from "fs-extra";
import * as path from "path";
import { TransformerConfig, StorageAdapter } from "./types";

export interface ConfigurationSource {
  /** Load configuration from source */
  load(): Promise<Partial<TransformerConfig>>;
  /** Save configuration to source */
  save?(config: Partial<TransformerConfig>): Promise<void>;
  /** Check if source exists */
  exists(): Promise<boolean>;
}

export interface ConfigValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * File-based configuration source
 */
export class FileConfigSource implements ConfigurationSource {
  private filePath: string;

  constructor(filePath: string) {
    this.filePath = path.resolve(filePath);
  }

  async load(): Promise<Partial<TransformerConfig>> {
    if (!(await this.exists())) {
      return {};
    }

    try {
      const content = await fs.readFile(this.filePath, "utf-8");
      return JSON.parse(content);
    } catch (error) {
      throw new Error(
        `Failed to load configuration from ${this.filePath}: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  async save(config: Partial<TransformerConfig>): Promise<void> {
    try {
      await fs.ensureDir(path.dirname(this.filePath));
      await fs.writeFile(
        this.filePath,
        JSON.stringify(config, null, 2),
        "utf-8",
      );
    } catch (error) {
      throw new Error(
        `Failed to save configuration to ${this.filePath}: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  async exists(): Promise<boolean> {
    return fs.pathExists(this.filePath);
  }
}

/**
 * Environment variable configuration source
 */
export class EnvConfigSource implements ConfigurationSource {
  private prefix: string;

  constructor(prefix: string = "TXTRANSFORMER_") {
    this.prefix = prefix;
  }

  async load(): Promise<Partial<TransformerConfig>> {
    const config: Partial<TransformerConfig> = {};

    // Python extractor URL
    const pythonUrl = process.env[`${this.prefix}PYTHON_URL`];
    if (pythonUrl) {
      config.pythonExtractorUrl = pythonUrl;
    }

    // Temporary directory
    const tempDir = process.env[`${this.prefix}TEMP_DIR`];
    if (tempDir) {
      config.tempDir = tempDir;
    }

    // Caching
    const enableCaching = process.env[`${this.prefix}ENABLE_CACHING`];
    if (enableCaching !== undefined) {
      config.enableCaching = enableCaching.toLowerCase() === "true";
    }

    // Timeout
    const timeout = process.env[`${this.prefix}TIMEOUT`];
    if (timeout) {
      const timeoutMs = parseInt(timeout, 10);
      if (!isNaN(timeoutMs)) {
        config.timeout = timeoutMs;
      }
    }

    // LLM configuration
    const llmProvider = process.env[`${this.prefix}LLM_PROVIDER`];
    const llmApiKey = process.env[`${this.prefix}LLM_API_KEY`];
    const llmModel = process.env[`${this.prefix}LLM_MODEL`];
    const llmBaseUrl = process.env[`${this.prefix}LLM_BASE_URL`];

    if (llmProvider || llmApiKey || llmModel || llmBaseUrl) {
      config.llm = {
        provider: llmProvider as any,
        apiKey: llmApiKey,
        modelName: llmModel,
        baseUrl: llmBaseUrl,
      };
    }

    // Storage configuration
    const storageType = process.env[`${this.prefix}STORAGE_TYPE`];
    if (storageType) {
      config.storage = {
        type: storageType as any,
      };
    }

    return config;
  }

  async exists(): Promise<boolean> {
    // Check if any environment variables with our prefix exist
    const envVars = Object.keys(process.env);
    return envVars.some((key) => key.startsWith(this.prefix));
  }
}

/**
 * Configuration manager with multiple sources and validation
 */
export class ConfigManager {
  private sources: ConfigurationSource[] = [];
  private cachedConfig?: TransformerConfig;
  private defaults: TransformerConfig;

  constructor(defaults?: Partial<TransformerConfig>) {
    this.defaults = {
      pythonExtractorUrl: "http://localhost:8000",
      tempDir: "./temp",
      enableCaching: true,
      timeout: 30000,
      ...defaults,
    };
  }

  /**
   * Add configuration source (order matters - later sources override earlier ones)
   */
  addSource(source: ConfigurationSource): void {
    this.sources.push(source);
    this.cachedConfig = undefined; // Invalidate cache
  }

  /**
   * Load configuration from all sources
   */
  async load(): Promise<TransformerConfig> {
    if (this.cachedConfig) {
      return this.cachedConfig;
    }

    let config: Partial<TransformerConfig> = { ...this.defaults };

    // Load from all sources in order
    for (const source of this.sources) {
      try {
        const sourceConfig = await source.load();
        config = this.mergeConfigs(config, sourceConfig);
      } catch (error) {
        console.warn(
          `Failed to load from configuration source: ${error instanceof Error ? error.message : "Unknown error"}`,
        );
      }
    }

    // Validate the final configuration
    const validation = this.validate(config);
    if (!validation.valid) {
      throw new Error(`Invalid configuration: ${validation.errors.join(", ")}`);
    }

    // Show warnings
    if (validation.warnings.length > 0) {
      console.warn("Configuration warnings:", validation.warnings);
    }

    this.cachedConfig = config as TransformerConfig;
    return this.cachedConfig;
  }

  /**
   * Save configuration to writable sources
   */
  async save(config: Partial<TransformerConfig>): Promise<void> {
    const savePromises = this.sources
      .filter((source) => source.save)
      .map((source) => source.save!(config));

    await Promise.all(savePromises);
    this.cachedConfig = undefined; // Invalidate cache
  }

  /**
   * Get current configuration (load if not cached)
   */
  async getConfig(): Promise<TransformerConfig> {
    return this.load();
  }

  /**
   * Update configuration and save to sources
   */
  async updateConfig(
    updates: Partial<TransformerConfig>,
  ): Promise<TransformerConfig> {
    const current = await this.load();
    const updated = this.mergeConfigs(current, updates);

    const validation = this.validate(updated);
    if (!validation.valid) {
      throw new Error(
        `Invalid configuration updates: ${validation.errors.join(", ")}`,
      );
    }

    await this.save(updates);
    this.cachedConfig = updated as TransformerConfig;
    return this.cachedConfig;
  }

  /**
   * Validate configuration
   */
  validate(config: Partial<TransformerConfig>): ConfigValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    // Validate required fields
    if (!config.tempDir) {
      errors.push("tempDir is required");
    }

    if (!config.timeout || config.timeout <= 0) {
      errors.push("timeout must be a positive number");
    }

    // Validate LLM configuration
    if (config.llm) {
      if (!config.llm.provider) {
        errors.push("llm.provider is required when LLM config is provided");
      }

      if (
        ["openai", "anthropic"].includes(config.llm.provider!) &&
        !config.llm.apiKey
      ) {
        errors.push("llm.apiKey is required for hosted LLM providers");
      }

      if (config.llm.provider === "ollama" && !config.llm.baseUrl) {
        warnings.push("llm.baseUrl not set for Ollama, using default");
      }
    }

    // Validate storage configuration
    if (config.storage) {
      if (!["filesystem", "memory", "custom"].includes(config.storage.type)) {
        errors.push("storage.type must be filesystem, memory, or custom");
      }

      if (config.storage.type === "custom" && !config.storage.adapter) {
        errors.push("storage.adapter is required when storage.type is custom");
      }
    }

    // Validate temp directory
    if (config.tempDir && !path.isAbsolute(config.tempDir)) {
      warnings.push(
        "tempDir should be an absolute path for better reliability",
      );
    }

    // Validate Python extractor URL
    if (config.pythonExtractorUrl) {
      try {
        new URL(config.pythonExtractorUrl);
      } catch {
        errors.push("pythonExtractorUrl must be a valid URL");
      }
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }

  /**
   * Reset cached configuration
   */
  clearCache(): void {
    this.cachedConfig = undefined;
  }

  /**
   * Get configuration schema for documentation/validation
   */
  getSchema(): any {
    return {
      type: "object",
      properties: {
        pythonExtractorUrl: {
          type: "string",
          format: "uri",
          description: "URL of the Python extractor service",
          default: "http://localhost:8000",
        },
        tempDir: {
          type: "string",
          description: "Directory for temporary files",
          default: "./temp",
        },
        enableCaching: {
          type: "boolean",
          description: "Enable file content caching",
          default: true,
        },
        timeout: {
          type: "number",
          minimum: 1000,
          description: "Request timeout in milliseconds",
          default: 30000,
        },
        llm: {
          type: "object",
          properties: {
            provider: {
              type: "string",
              enum: ["openai", "anthropic", "ollama", "local"],
              description: "LLM provider",
            },
            apiKey: {
              type: "string",
              description: "API key for hosted providers",
            },
            modelName: {
              type: "string",
              description: "Model name/identifier",
            },
            baseUrl: {
              type: "string",
              format: "uri",
              description: "Base URL for self-hosted providers",
            },
          },
        },
        storage: {
          type: "object",
          properties: {
            type: {
              type: "string",
              enum: ["filesystem", "memory", "custom"],
              description: "Storage adapter type",
            },
          },
        },
      },
      required: ["tempDir", "timeout"],
    };
  }

  /**
   * Merge two configuration objects
   */
  private mergeConfigs(
    base: Partial<TransformerConfig>,
    override: Partial<TransformerConfig>,
  ): Partial<TransformerConfig> {
    const merged = { ...base };

    for (const [key, value] of Object.entries(override)) {
      if (value !== undefined) {
        if (
          key === "llm" &&
          typeof value === "object" &&
          typeof merged.llm === "object"
        ) {
          merged.llm = { ...merged.llm, ...value };
        } else if (
          key === "storage" &&
          typeof value === "object" &&
          typeof merged.storage === "object"
        ) {
          merged.storage = { ...merged.storage, ...value };
        } else {
          (merged as any)[key] = value;
        }
      }
    }

    return merged;
  }
}

/**
 * Create a standard configuration manager with common sources
 */
export function createStandardConfigManager(
  options: {
    configFile?: string;
    envPrefix?: string;
    defaults?: Partial<TransformerConfig>;
  } = {},
): ConfigManager {
  const {
    configFile = "./txtransformer.config.json",
    envPrefix = "TXTRANSFORMER_",
    defaults = {},
  } = options;

  const manager = new ConfigManager(defaults);

  // Add file-based configuration (if file exists)
  manager.addSource(new FileConfigSource(configFile));

  // Add environment variable configuration
  manager.addSource(new EnvConfigSource(envPrefix));

  return manager;
}

/**
 * Create configuration from multiple sources with validation
 */
export async function loadConfig(
  sources: {
    file?: string;
    env?: boolean | string;
    defaults?: Partial<TransformerConfig>;
  } = {},
): Promise<TransformerConfig> {
  const manager = new ConfigManager(sources.defaults);

  // Add file source
  if (sources.file) {
    manager.addSource(new FileConfigSource(sources.file));
  }

  // Add environment source
  if (sources.env !== false) {
    const prefix =
      typeof sources.env === "string" ? sources.env : "TXTRANSFORMER_";
    manager.addSource(new EnvConfigSource(prefix));
  }

  return manager.load();
}
