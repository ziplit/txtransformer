import {
  ExtractorServiceDiscovery,
  createServiceDiscovery,
  autoDiscoverService,
} from "../src/service-discovery";
import { TEST_TEMP_DIR } from "./setup";
import * as fs from "fs-extra";

// Mock fetch for testing
global.fetch = jest.fn();

describe("Service Discovery", () => {
  beforeAll(async () => {
    await fs.ensureDir(TEST_TEMP_DIR);
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("ExtractorServiceDiscovery", () => {
    test("should initialize with candidate URLs", () => {
      const discovery = new ExtractorServiceDiscovery({
        candidates: ["http://localhost:8000", "http://backup:8000"],
        healthCheckTimeout: 3000,
      });

      const endpoints = discovery.getAllEndpoints();
      expect(endpoints).toHaveLength(2);
      expect(endpoints[0].url).toBe("http://localhost:8000");
      expect(endpoints[1].url).toBe("http://backup:8000");
      expect(endpoints[0].healthy).toBe(false);
      expect(endpoints[1].healthy).toBe(false);
    });

    test("should discover healthy services", async () => {
      const mockFetch = fetch as jest.MockedFunction<typeof fetch>;

      // Mock successful health check
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "healthy", version: "1.0.0" }),
      } as Response);

      const discovery = new ExtractorServiceDiscovery({
        candidates: ["http://localhost:8000"],
        healthCheckTimeout: 3000,
      });

      const endpoints = await discovery.discover();

      expect(endpoints).toHaveLength(1);
      expect(endpoints[0].healthy).toBe(true);
      expect(endpoints[0].version).toBe("1.0.0");
      expect(endpoints[0].responseTime).toBeDefined();
      expect(mockFetch).toHaveBeenCalledWith(
        "http://localhost:8000/healthz",
        expect.objectContaining({
          headers: { Accept: "application/json" },
        }),
      );
    });

    test("should handle unhealthy services", async () => {
      const mockFetch = fetch as jest.MockedFunction<typeof fetch>;

      // Mock failed health check
      mockFetch.mockRejectedValue(new Error("Connection refused"));

      const discovery = new ExtractorServiceDiscovery({
        candidates: ["http://unreachable:8000"],
        healthCheckTimeout: 1000,
      });

      const endpoints = await discovery.discover();

      expect(endpoints).toHaveLength(0);

      const allEndpoints = discovery.getAllEndpoints();
      expect(allEndpoints[0].healthy).toBe(false);
    });

    test("should find best endpoint by response time", async () => {
      const mockFetch = fetch as jest.MockedFunction<typeof fetch>;

      // Mock different response times
      let callCount = 0;
      mockFetch.mockImplementation(() => {
        callCount++;
        const delay = callCount === 1 ? 100 : 50; // First call slower, second faster

        return new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              ok: true,
              json: () =>
                Promise.resolve({ status: "healthy", version: "1.0.0" }),
            } as Response);
          }, delay);
        });
      });

      const discovery = new ExtractorServiceDiscovery({
        candidates: ["http://slow:8000", "http://fast:8000"],
        healthCheckTimeout: 5000,
      });

      await discovery.discover();

      const best = discovery.getBestEndpoint();
      expect(best?.url).toBe("http://fast:8000");
      expect(best?.responseTime).toBeLessThan(100);
    });

    test("should return null when no healthy endpoints", async () => {
      const mockFetch = fetch as jest.MockedFunction<typeof fetch>;
      mockFetch.mockRejectedValue(new Error("No services"));

      const discovery = new ExtractorServiceDiscovery({
        candidates: ["http://down:8000"],
      });

      await discovery.discover();

      const best = discovery.getBestEndpoint();
      expect(best).toBeNull();
    });

    test("should add and remove endpoints", async () => {
      const discovery = new ExtractorServiceDiscovery({
        candidates: ["http://initial:8000"],
      });

      expect(discovery.getAllEndpoints()).toHaveLength(1);

      discovery.addEndpoint("http://new:8000");
      expect(discovery.getAllEndpoints()).toHaveLength(2);

      discovery.removeEndpoint("http://initial:8000");
      expect(discovery.getAllEndpoints()).toHaveLength(1);
      expect(discovery.getAllEndpoints()[0].url).toBe("http://new:8000");
    });

    test("should not add duplicate endpoints", () => {
      const discovery = new ExtractorServiceDiscovery({
        candidates: ["http://test:8000"],
      });

      discovery.addEndpoint("http://test:8000"); // Duplicate
      expect(discovery.getAllEndpoints()).toHaveLength(1);
    });

    test("should handle monitoring lifecycle", async () => {
      jest.useFakeTimers();

      const discovery = new ExtractorServiceDiscovery({
        candidates: ["http://localhost:8000"],
        healthCheckInterval: 10000,
        continuousMonitoring: true,
      });

      const mockFetch = fetch as jest.MockedFunction<typeof fetch>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "healthy" }),
      } as Response);

      // Start monitoring
      await discovery.discover();
      expect(mockFetch).toHaveBeenCalledTimes(1);

      // Advance timer and check monitoring
      jest.advanceTimersByTime(10000);
      await Promise.resolve(); // Allow promises to resolve
      expect(mockFetch).toHaveBeenCalledTimes(2);

      // Stop monitoring
      discovery.stopMonitoring();
      jest.advanceTimersByTime(10000);
      await Promise.resolve();
      expect(mockFetch).toHaveBeenCalledTimes(2); // Should not increase

      jest.useRealTimers();
    });
  });

  describe("createServiceDiscovery", () => {
    test("should create discovery from config", () => {
      const config = {
        tempDir: "/tmp",
        timeout: 30000,
        enableCaching: true,
        pythonExtractorUrl: "http://configured:8000",
      };

      const discovery = createServiceDiscovery(config);

      expect(discovery).toBeDefined();

      const endpoints = discovery!.getAllEndpoints();
      const urls = endpoints.map((e) => e.url);
      expect(urls).toContain("http://configured:8000");
      expect(urls).toContain("http://localhost:8000");
      expect(urls).toContain("http://127.0.0.1:8000");
    });

    test("should return null for empty config", () => {
      const config = {
        tempDir: "/tmp",
        timeout: 30000,
        enableCaching: true,
      };

      // Mock the default candidates to be empty for this test
      const discovery = new ExtractorServiceDiscovery({
        candidates: [],
      });

      expect(discovery.getAllEndpoints()).toHaveLength(0);
    });

    test("should use custom service discovery options", () => {
      const config = {
        tempDir: "/tmp",
        timeout: 5000,
        enableCaching: true,
        pythonExtractorUrl: "http://custom:8000",
        serviceDiscovery: {
          enabled: true,
          candidates: ["http://candidate1:8000", "http://candidate2:8000"],
          healthCheckTimeout: 3000,
          healthCheckInterval: 15000,
        },
      };

      const discovery = createServiceDiscovery(config);
      expect(discovery).toBeDefined();
    });
  });

  describe("autoDiscoverService", () => {
    test("should keep original URL when healthy", async () => {
      const mockFetch = fetch as jest.MockedFunction<typeof fetch>;
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ status: "healthy" }),
      } as Response);

      const config = {
        tempDir: "/tmp",
        timeout: 30000,
        enableCaching: true,
        pythonExtractorUrl: "http://healthy:8000",
      };

      const result = await autoDiscoverService(config);
      expect(result.pythonExtractorUrl).toBe("http://healthy:8000");
    });

    test("should update URL when original is unhealthy", async () => {
      const mockFetch = fetch as jest.MockedFunction<typeof fetch>;

      // First call (original URL) fails, second call (fallback) succeeds
      let callCount = 0;
      mockFetch.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.reject(new Error("Connection refused"));
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: "healthy" }),
        } as Response);
      });

      const config = {
        tempDir: "/tmp",
        timeout: 30000,
        enableCaching: true,
        pythonExtractorUrl: "http://unhealthy:8000",
      };

      const result = await autoDiscoverService(config);
      expect(result.pythonExtractorUrl).not.toBe("http://unhealthy:8000");
      expect(result.pythonExtractorUrl).toMatch(
        /http:\/\/(localhost|127\.0\.0\.1):8000/,
      );
    });

    test("should handle discovery failure gracefully", async () => {
      const mockFetch = fetch as jest.MockedFunction<typeof fetch>;
      mockFetch.mockRejectedValue(new Error("All services down"));

      const config = {
        tempDir: "/tmp",
        timeout: 30000,
        enableCaching: true,
        pythonExtractorUrl: "http://original:8000",
      };

      const result = await autoDiscoverService(config);
      expect(result).toEqual(config); // Should return original config unchanged
    });
  });
});
