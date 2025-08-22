import * as fs from "fs-extra";
import * as path from "path";
import {
  ConfigManager,
  FileConfigSource,
  EnvConfigSource,
  createStandardConfigManager,
  loadConfig,
} from "../src/config";
import { TransformerConfig } from "../src/types";
import { TEST_TEMP_DIR } from "./setup";

describe("Configuration Management", () => {
  describe("FileConfigSource", () => {
    let configFile: string;
    let source: FileConfigSource;

    beforeEach(() => {
      configFile = path.join(TEST_TEMP_DIR, "test-config.json");
      source = new FileConfigSource(configFile);
    });

    afterEach(async () => {
      try {
        await fs.remove(configFile);
      } catch (error) {
        // Ignore cleanup errors
      }
    });

    test("should return empty config for non-existent file", async () => {
      const config = await source.load();
      expect(config).toEqual({});
    });

    test("should save and load configuration", async () => {
      const testConfig: Partial<TransformerConfig> = {
        tempDir: "/tmp/test",
        enableCaching: false,
        timeout: 5000,
      };

      await source.save(testConfig);
      expect(await source.exists()).toBe(true);

      const loaded = await source.load();
      expect(loaded).toEqual(testConfig);
    });

    test("should handle JSON parsing errors", async () => {
      // Write invalid JSON
      await fs.writeFile(configFile, "invalid json content");

      await expect(source.load()).rejects.toThrow();
    });
  });

  describe("EnvConfigSource", () => {
    let source: EnvConfigSource;
    const originalEnv = process.env;

    beforeEach(() => {
      source = new EnvConfigSource("TEST_");
      // Clear test environment variables
      Object.keys(process.env).forEach((key) => {
        if (key.startsWith("TEST_")) {
          delete process.env[key];
        }
      });
    });

    afterEach(() => {
      process.env = originalEnv;
    });

    test("should return empty config when no env vars present", async () => {
      const config = await source.load();
      expect(config).toEqual({});
    });

    test("should load configuration from environment variables", async () => {
      process.env.TEST_PYTHON_URL = "http://localhost:9000";
      process.env.TEST_TEMP_DIR = "/tmp/test-env";
      process.env.TEST_ENABLE_CACHING = "false";
      process.env.TEST_TIMEOUT = "15000";
      process.env.TEST_LLM_PROVIDER = "openai";
      process.env.TEST_LLM_API_KEY = "test-key";

      const config = await source.load();

      expect(config.pythonExtractorUrl).toBe("http://localhost:9000");
      expect(config.tempDir).toBe("/tmp/test-env");
      expect(config.enableCaching).toBe(false);
      expect(config.timeout).toBe(15000);
      expect(config.llm?.provider).toBe("openai");
      expect(config.llm?.apiKey).toBe("test-key");
    });

    test("should handle boolean conversion", async () => {
      process.env.TEST_ENABLE_CACHING = "true";

      const config = await source.load();
      expect(config.enableCaching).toBe(true);

      process.env.TEST_ENABLE_CACHING = "false";
      const config2 = await source.load();
      expect(config2.enableCaching).toBe(false);
    });

    test("should handle number conversion", async () => {
      process.env.TEST_TIMEOUT = "12345";

      const config = await source.load();
      expect(config.timeout).toBe(12345);

      process.env.TEST_TIMEOUT = "invalid";
      const config2 = await source.load();
      expect(config2.timeout).toBeUndefined();
    });

    test("should detect existence of env vars", async () => {
      expect(await source.exists()).toBe(false);

      process.env.TEST_TEMP_DIR = "/tmp/test";
      expect(await source.exists()).toBe(true);
    });
  });

  describe("ConfigManager", () => {
    let manager: ConfigManager;

    beforeEach(() => {
      manager = new ConfigManager({
        tempDir: TEST_TEMP_DIR,
        timeout: 5000,
        enableCaching: true,
      });
    });

    test("should load default configuration", async () => {
      const config = await manager.load();

      expect(config.tempDir).toBe(TEST_TEMP_DIR);
      expect(config.timeout).toBe(5000);
      expect(config.enableCaching).toBe(true);
    });

    test("should merge configurations from multiple sources", async () => {
      const configFile = path.join(TEST_TEMP_DIR, "multi-test-config.json");
      const fileSource = new FileConfigSource(configFile);

      // Save file config
      await fileSource.save({
        tempDir: "/file/temp",
        timeout: 10000,
      });

      manager.addSource(fileSource);

      const config = await manager.load();

      expect(config.tempDir).toBe("/file/temp"); // From file
      expect(config.timeout).toBe(10000); // From file
      expect(config.enableCaching).toBe(true); // From defaults

      // Cleanup
      try {
        await fs.remove(configFile);
      } catch (error) {
        // Ignore
      }
    });

    test("should validate configuration", () => {
      const validConfig: Partial<TransformerConfig> = {
        tempDir: "/tmp/valid",
        timeout: 5000,
        pythonExtractorUrl: "http://localhost:8000",
      };

      const validation = manager.validate(validConfig);
      expect(validation.valid).toBe(true);
      expect(validation.errors).toHaveLength(0);
    });

    test("should detect invalid configuration", () => {
      const invalidConfig: Partial<TransformerConfig> = {
        tempDir: "", // Invalid: empty
        timeout: -1, // Invalid: negative
        pythonExtractorUrl: "not-a-url", // Invalid: malformed URL
      };

      const validation = manager.validate(invalidConfig);
      expect(validation.valid).toBe(false);
      expect(validation.errors.length).toBeGreaterThan(0);
    });

    test("should update configuration", async () => {
      const updates: Partial<TransformerConfig> = {
        timeout: 15000,
        enableCaching: false,
      };

      const updated = await manager.updateConfig(updates);

      expect(updated.timeout).toBe(15000);
      expect(updated.enableCaching).toBe(false);
      expect(updated.tempDir).toBe(TEST_TEMP_DIR); // Should keep existing
    });

    test("should provide configuration schema", () => {
      const schema = manager.getSchema();

      expect(schema).toBeDefined();
      expect(schema.type).toBe("object");
      expect(schema.properties).toBeDefined();
      expect(schema.properties.tempDir).toBeDefined();
      expect(schema.properties.timeout).toBeDefined();
    });
  });

  describe("createStandardConfigManager", () => {
    test("should create manager with default options", () => {
      const manager = createStandardConfigManager();
      expect(manager).toBeInstanceOf(ConfigManager);
    });

    test("should create manager with custom options", () => {
      const manager = createStandardConfigManager({
        configFile: "custom-config.json",
        envPrefix: "CUSTOM_",
        defaults: { timeout: 20000 },
      });

      expect(manager).toBeInstanceOf(ConfigManager);
    });
  });

  describe("loadConfig", () => {
    test("should load config with defaults only", async () => {
      const config = await loadConfig({
        env: false, // Disable env loading
        defaults: {
          tempDir: TEST_TEMP_DIR,
          timeout: 8000,
          enableCaching: true,
        },
      });

      expect(config.tempDir).toBe(TEST_TEMP_DIR);
      expect(config.timeout).toBe(8000);
      expect(config.enableCaching).toBe(true);
    });

    test("should load config from file", async () => {
      const configFile = path.join(TEST_TEMP_DIR, "load-test-config.json");
      await fs.ensureDir(TEST_TEMP_DIR);
      await fs.writeFile(
        configFile,
        JSON.stringify({
          tempDir: "/loaded/temp",
          timeout: 12000,
        }),
      );

      const config = await loadConfig({
        file: configFile,
        env: false,
        defaults: {
          tempDir: "/default/temp",
          timeout: 5000,
          enableCaching: true,
        },
      });

      expect(config.tempDir).toBe("/loaded/temp");
      expect(config.timeout).toBe(12000);
      expect(config.enableCaching).toBe(true); // From defaults

      // Cleanup
      try {
        await fs.remove(configFile);
      } catch (error) {
        // Ignore
      }
    });
  });

  describe("Enhanced Configuration Features", () => {
    let manager: ConfigManager;

    beforeEach(() => {
      manager = new ConfigManager({
        tempDir: TEST_TEMP_DIR,
        timeout: 30000,
        enableCaching: true,
      });
    });

    test("should validate service discovery configuration", () => {
      const configWithServiceDiscovery: Partial<TransformerConfig> = {
        tempDir: TEST_TEMP_DIR,
        timeout: 30000,
        serviceDiscovery: {
          enabled: true,
          candidates: ["http://localhost:8000", "invalid-url"],
          healthCheckTimeout: 500, // Too low
          healthCheckInterval: 1000, // Too low
        },
      };

      const validation = manager.validate(configWithServiceDiscovery);
      expect(validation.valid).toBe(false);
      expect(validation.errors).toContain(
        "Invalid service discovery candidate URL: invalid-url",
      );
      expect(validation.errors).toContain(
        "serviceDiscovery.healthCheckTimeout must be at least 1000ms",
      );
      expect(validation.errors).toContain(
        "serviceDiscovery.healthCheckInterval must be at least 5000ms",
      );
    });

    test("should merge service discovery configuration correctly", () => {
      const base = {
        serviceDiscovery: {
          enabled: true,
          candidates: ["http://localhost:8000"],
        },
      };

      const override = {
        serviceDiscovery: {
          healthCheckTimeout: 5000,
          candidates: ["http://override:8000"],
        },
      };

      const merged = manager["mergeConfigs"](base, override);
      expect(merged.serviceDiscovery).toEqual({
        enabled: true,
        candidates: ["http://override:8000"],
        healthCheckTimeout: 5000,
      });
    });

    test("should include service discovery in schema", () => {
      const schema = manager.getSchema();
      expect(schema.properties.serviceDiscovery).toBeDefined();
      expect(
        schema.properties.serviceDiscovery.properties.enabled,
      ).toBeDefined();
      expect(
        schema.properties.serviceDiscovery.properties.candidates,
      ).toBeDefined();
    });
  });

  describe("Environment Variables - Service Discovery", () => {
    let source: EnvConfigSource;
    const originalEnv = process.env;

    beforeEach(() => {
      source = new EnvConfigSource("TEST_SD_");
      // Clear test environment variables
      Object.keys(process.env).forEach((key) => {
        if (key.startsWith("TEST_SD_")) {
          delete process.env[key];
        }
      });
    });

    afterEach(() => {
      process.env = originalEnv;
    });

    test("should load service discovery from environment variables", async () => {
      process.env.TEST_SD_SERVICE_DISCOVERY_ENABLED = "true";
      process.env.TEST_SD_SERVICE_DISCOVERY_CANDIDATES =
        "http://svc1:8000,http://svc2:8000";
      process.env.TEST_SD_SERVICE_DISCOVERY_TIMEOUT = "3000";
      process.env.TEST_SD_SERVICE_DISCOVERY_INTERVAL = "15000";

      const config = await source.load();

      expect(config.serviceDiscovery?.enabled).toBe(true);
      expect(config.serviceDiscovery?.candidates).toEqual([
        "http://svc1:8000",
        "http://svc2:8000",
      ]);
      expect(config.serviceDiscovery?.healthCheckTimeout).toBe(3000);
      expect(config.serviceDiscovery?.healthCheckInterval).toBe(15000);
    });

    test("should handle partial service discovery configuration", async () => {
      process.env.TEST_SD_SERVICE_DISCOVERY_ENABLED = "false";

      const config = await source.load();
      expect(config.serviceDiscovery?.enabled).toBe(false);
      expect(config.serviceDiscovery?.candidates).toBeUndefined();
    });

    test("should ignore invalid timeout values", async () => {
      process.env.TEST_SD_SERVICE_DISCOVERY_TIMEOUT = "invalid";
      process.env.TEST_SD_SERVICE_DISCOVERY_INTERVAL = "not-a-number";

      const config = await source.load();
      expect(config.serviceDiscovery?.healthCheckTimeout).toBeUndefined();
      expect(config.serviceDiscovery?.healthCheckInterval).toBeUndefined();
    });
  });
});
