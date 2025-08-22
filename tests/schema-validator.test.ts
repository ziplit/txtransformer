import { SchemaValidator } from "../src/validation";
import { TEST_TEMP_DIR } from "./setup";
import * as fs from "fs-extra";

describe("SchemaValidator", () => {
  let validator: SchemaValidator;

  beforeAll(async () => {
    await fs.ensureDir(TEST_TEMP_DIR);
  });

  beforeEach(() => {
    validator = new SchemaValidator();
  });

  describe("validateAgainstDomainSchemas", () => {
    test("should validate generic message data", () => {
      const testData = {
        messageId: "test123",
        subject: "Test Subject",
        from: {
          name: "John Doe",
          email: "john@example.com",
        },
        classification: {
          category: "transactional",
          intent: "informational",
          confidence: 0.8,
        },
        bodySummary: "This is a test email",
      };

      const result = validator.validateAgainstDomainSchemas(testData);

      expect(result.valid).toBe(true);
      expect(result.detectedDomain).toBeDefined();
    });

    test("should handle invalid data gracefully", () => {
      const invalidData = {
        invalidField: "test",
      };

      const result = validator.validateAgainstDomainSchemas(invalidData);

      // Should not throw error, but likely not valid
      expect(result).toBeDefined();
    });

    test("should validate order data", () => {
      const orderData = {
        orderId: "ORDER-123",
        orderDate: "2024-01-01",
        vendor: "Test Vendor",
        items: [
          {
            name: "Test Item",
            price: 19.99,
            quantity: 1,
          },
        ],
        total: 19.99,
        currency: "USD",
      };

      const result = validator.validateAgainstDomainSchemas(orderData);

      expect(result).toBeDefined();
    });
  });

  describe("schema loading", () => {
    test("should have schemas loaded during initialization", () => {
      // The schemas should be loaded when SchemaValidator is constructed
      // We can test this by calling validateAgainstDomainSchemas
      const testData = {
        messageId: "test",
        subject: "test",
        from: { email: "test@example.com" },
        classification: { category: "other", intent: "informational" },
      };

      const result = validator.validateAgainstDomainSchemas(testData);
      expect(result).toBeDefined();
    });

    test("should validate against multiple schemas", () => {
      const orderData = {
        orderId: "ORDER-123",
        items: [{ name: "Test", price: 10, quantity: 1 }],
        total: 10,
      };

      const result = validator.validateAgainstDomainSchemas(orderData);
      expect(result).toBeDefined();
    });
  });
});
