import {
  ConfigManager,
  FileConfigSource,
  EnvConfigSource,
  createStandardConfigManager,
  ExtractorServiceDiscovery,
  autoDiscoverService,
  createServiceDiscovery,
  loadConfig,
  createLogger,
} from "../src";

async function configurationExample() {
  const logger = createLogger({
    level: "info",
    pretty: true,
    name: "config-example",
  });

  logger.info("🔧 Advanced Configuration Management Example");

  // Example 1: Basic configuration loading from multiple sources
  logger.info("--- Example 1: Multi-source Configuration ---");

  const config1 = await loadConfig({
    file: "./txtransformer.config.json",
    env: true,
    defaults: {
      tempDir: "./temp",
      timeout: 30000,
      enableCaching: true,
      llm: {
        provider: "local",
      },
    },
  });

  logger.info("Loaded configuration:");
  console.log(JSON.stringify(config1, null, 2));

  // Example 2: Configuration manager with custom sources
  logger.info("--- Example 2: Custom Configuration Manager ---");

  const configManager = new ConfigManager({
    tempDir: "./temp",
    timeout: 30000,
    enableCaching: true,
  });

  // Add custom configuration file
  configManager.addSource(new FileConfigSource("./custom-config.json"));

  // Add environment variables with custom prefix
  configManager.addSource(new EnvConfigSource("CUSTOM_"));

  const config2 = await configManager.load();

  logger.info("Configuration from manager:");
  console.log(JSON.stringify(config2, null, 2));

  // Example 3: Configuration validation
  logger.info("--- Example 3: Configuration Validation ---");

  const testConfig = {
    tempDir: "", // Invalid
    timeout: -1, // Invalid
    pythonExtractorUrl: "not-a-url", // Invalid
    llm: {
      provider: "openai" as const,
      // Missing apiKey - should warn
    },
  };

  const validation = configManager.validate(testConfig);

  logger.info(
    `Validation result: ${validation.valid ? "✅ Valid" : "❌ Invalid"}`,
  );
  if (validation.errors.length > 0) {
    logger.error("Validation errors:", validation.errors);
  }
  if (validation.warnings.length > 0) {
    logger.warn("Validation warnings:", validation.warnings);
  }

  // Example 4: Service Discovery
  logger.info("--- Example 4: Service Discovery ---");

  // Create service discovery with multiple candidates
  const serviceDiscovery = new ExtractorServiceDiscovery({
    candidates: [
      "http://localhost:8000",
      "http://127.0.0.1:8000",
      "http://python-extractor:8000",
      "http://backup-extractor:8000",
    ],
    healthCheckTimeout: 3000,
    healthCheckInterval: 15000,
    continuousMonitoring: false,
  });

  try {
    logger.info("🔍 Discovering available services...");
    const endpoints = await serviceDiscovery.discover();

    logger.info(`Found ${endpoints.length} healthy service(s):`);
    endpoints.forEach((endpoint) => {
      logger.info(
        `  • ${endpoint.url} (${endpoint.responseTime}ms, v${endpoint.version})`,
      );
    });

    const bestEndpoint = serviceDiscovery.getBestEndpoint();
    if (bestEndpoint) {
      logger.info(`🚀 Best endpoint: ${bestEndpoint.url}`);
    } else {
      logger.warn("⚠️ No healthy services found");
    }
  } catch (error) {
    logger.error("Service discovery failed:", error);
  }

  // Example 5: Auto-discovery and configuration update
  logger.info("--- Example 5: Auto-discovery Configuration ---");

  const baseConfig = {
    tempDir: "./temp",
    timeout: 30000,
    enableCaching: true,
    pythonExtractorUrl: "http://localhost:9999", // Will be updated if unavailable
  };

  logger.info("Original configuration:");
  console.log(`Python Extractor URL: ${baseConfig.pythonExtractorUrl}`);

  try {
    const discoveredConfig = await autoDiscoverService(baseConfig);

    if (discoveredConfig.pythonExtractorUrl !== baseConfig.pythonExtractorUrl) {
      logger.info(
        `🔄 Auto-discovered service: ${discoveredConfig.pythonExtractorUrl}`,
      );
    } else {
      logger.info("✅ Original service URL is healthy");
    }
  } catch (error) {
    logger.error("Auto-discovery failed:", error);
  }

  // Example 6: Configuration Schema
  logger.info("--- Example 6: Configuration Schema ---");

  const schema = configManager.getSchema();
  logger.info("Configuration schema properties:");
  Object.keys(schema.properties).forEach((prop) => {
    const propSchema = schema.properties[prop];
    logger.info(`  • ${prop}: ${propSchema.description}`);
  });

  // Example 7: Environment Variable Configuration
  logger.info("--- Example 7: Environment Variables ---");

  // Set some environment variables (in real usage, these would be set externally)
  const originalEnv = { ...process.env };

  // Simulate environment variables
  process.env.TXTRANSFORMER_PYTHON_URL = "http://localhost:8080";
  process.env.TXTRANSFORMER_TEMP_DIR = "/tmp/txtransformer";
  process.env.TXTRANSFORMER_ENABLE_CACHING = "false";
  process.env.TXTRANSFORMER_LLM_PROVIDER = "anthropic";
  process.env.TXTRANSFORMER_LLM_API_KEY = "sk-test-key";
  process.env.TXTRANSFORMER_SERVICE_DISCOVERY_ENABLED = "true";
  process.env.TXTRANSFORMER_SERVICE_DISCOVERY_CANDIDATES =
    "http://localhost:8000,http://backup:8000";

  const envConfig = await loadConfig({
    env: true,
    defaults: {
      tempDir: "./default-temp",
      timeout: 30000,
      enableCaching: true,
    },
  });

  logger.info("Configuration from environment variables:");
  console.log(JSON.stringify(envConfig, null, 2));

  // Restore original environment
  process.env = originalEnv;

  logger.info("✅ Configuration management examples completed!");
}

// Run the example
if (require.main === module) {
  configurationExample().catch((error) => {
    console.error("Example failed:", error);
    process.exit(1);
  });
}
