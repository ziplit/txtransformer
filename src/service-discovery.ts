import { TransformerConfig } from "./types";

export interface ServiceEndpoint {
  /** Service URL */
  url: string;
  /** Service health status */
  healthy: boolean;
  /** Response time in milliseconds */
  responseTime?: number;
  /** Service version */
  version?: string;
  /** Last health check timestamp */
  lastCheck?: number;
}

export interface ServiceDiscoveryOptions {
  /** List of candidate URLs to check */
  candidates: string[];
  /** Health check timeout in milliseconds */
  healthCheckTimeout?: number;
  /** Health check interval in milliseconds */
  healthCheckInterval?: number;
  /** Whether to continuously monitor service health */
  continuousMonitoring?: boolean;
}

/**
 * Service discovery for Python extractor services
 */
export class ExtractorServiceDiscovery {
  private endpoints: Map<string, ServiceEndpoint> = new Map();
  private options: Required<ServiceDiscoveryOptions>;
  private monitoringInterval?: NodeJS.Timeout;

  constructor(options: ServiceDiscoveryOptions) {
    this.options = {
      healthCheckTimeout: 5000,
      healthCheckInterval: 30000,
      continuousMonitoring: false,
      ...options,
    };

    // Initialize endpoints
    for (const url of this.options.candidates) {
      this.endpoints.set(url, {
        url,
        healthy: false,
      });
    }
  }

  /**
   * Discover available services by checking health endpoints
   */
  async discover(): Promise<ServiceEndpoint[]> {
    const healthChecks = Array.from(this.endpoints.keys()).map((url) =>
      this.checkServiceHealth(url),
    );

    await Promise.allSettled(healthChecks);

    // Start continuous monitoring if enabled
    if (this.options.continuousMonitoring && !this.monitoringInterval) {
      this.startMonitoring();
    }

    return this.getHealthyEndpoints();
  }

  /**
   * Get the best available service endpoint
   */
  getBestEndpoint(): ServiceEndpoint | null {
    const healthy = this.getHealthyEndpoints();

    if (healthy.length === 0) {
      return null;
    }

    // Sort by response time (fastest first)
    healthy.sort((a, b) => {
      const aTime = a.responseTime || Infinity;
      const bTime = b.responseTime || Infinity;
      return aTime - bTime;
    });

    return healthy[0];
  }

  /**
   * Get all healthy endpoints
   */
  getHealthyEndpoints(): ServiceEndpoint[] {
    return Array.from(this.endpoints.values()).filter(
      (endpoint) => endpoint.healthy,
    );
  }

  /**
   * Check health of a specific service
   */
  async checkServiceHealth(url: string): Promise<ServiceEndpoint> {
    const endpoint = this.endpoints.get(url);
    if (!endpoint) {
      throw new Error(`Unknown endpoint: ${url}`);
    }

    const startTime = Date.now();

    try {
      // Check the health endpoint
      const healthUrl = new URL("/healthz", url).toString();
      const controller = new AbortController();
      const timeoutId = setTimeout(
        () => controller.abort(),
        this.options.healthCheckTimeout,
      );

      const response = await fetch(healthUrl, {
        signal: controller.signal,
        headers: {
          Accept: "application/json",
        },
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status}`);
      }

      const healthData = (await response.json()) as any;
      const responseTime = Date.now() - startTime;

      // Update endpoint status
      const updatedEndpoint: ServiceEndpoint = {
        url,
        healthy: true,
        responseTime,
        version: healthData.version || "unknown",
        lastCheck: Date.now(),
      };

      this.endpoints.set(url, updatedEndpoint);
      return updatedEndpoint;
    } catch (error) {
      // Mark as unhealthy
      const updatedEndpoint: ServiceEndpoint = {
        url,
        healthy: false,
        lastCheck: Date.now(),
      };

      this.endpoints.set(url, updatedEndpoint);
      return updatedEndpoint;
    }
  }

  /**
   * Start continuous health monitoring
   */
  private startMonitoring(): void {
    this.monitoringInterval = setInterval(async () => {
      const healthChecks = Array.from(this.endpoints.keys()).map((url) =>
        this.checkServiceHealth(url),
      );

      await Promise.allSettled(healthChecks);
    }, this.options.healthCheckInterval);
  }

  /**
   * Stop continuous health monitoring
   */
  stopMonitoring(): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = undefined;
    }
  }

  /**
   * Add a new service endpoint candidate
   */
  addEndpoint(url: string): void {
    if (!this.endpoints.has(url)) {
      this.endpoints.set(url, {
        url,
        healthy: false,
      });
    }
  }

  /**
   * Remove a service endpoint
   */
  removeEndpoint(url: string): void {
    this.endpoints.delete(url);
  }

  /**
   * Get all endpoints (healthy and unhealthy)
   */
  getAllEndpoints(): ServiceEndpoint[] {
    return Array.from(this.endpoints.values());
  }
}

/**
 * Create service discovery from configuration
 */
export function createServiceDiscovery(
  config: TransformerConfig,
): ExtractorServiceDiscovery | null {
  const candidates: string[] = [];

  // Add configured Python extractor URL
  if (config.pythonExtractorUrl) {
    candidates.push(config.pythonExtractorUrl);
  }

  // Add common default URLs for development
  const defaultCandidates = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://python-extractor:8000", // Docker compose service name
  ];

  // Only add defaults that aren't already in the candidates
  for (const url of defaultCandidates) {
    if (!candidates.includes(url)) {
      candidates.push(url);
    }
  }

  if (candidates.length === 0) {
    return null;
  }

  return new ExtractorServiceDiscovery({
    candidates,
    healthCheckTimeout: config.timeout || 5000,
    healthCheckInterval: 30000,
    continuousMonitoring: true,
  });
}

/**
 * Auto-discover and update configuration with best service endpoint
 */
export async function autoDiscoverService(
  config: TransformerConfig,
): Promise<TransformerConfig> {
  const discovery = createServiceDiscovery(config);

  if (!discovery) {
    return config;
  }

  try {
    await discovery.discover();
    const bestEndpoint = discovery.getBestEndpoint();

    if (bestEndpoint) {
      return {
        ...config,
        pythonExtractorUrl: bestEndpoint.url,
      };
    }
  } catch (error) {
    console.warn(
      "Service discovery failed:",
      error instanceof Error ? error.message : "Unknown error",
    );
  } finally {
    discovery.stopMonitoring();
  }

  return config;
}
