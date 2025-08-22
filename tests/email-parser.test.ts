import { EmailParser } from "../src/email-parser";
import { TEST_EMAIL_CONTENT, TEST_EMAIL_WITH_ATTACHMENT } from "./setup";

describe("EmailParser", () => {
  let parser: EmailParser;

  beforeEach(() => {
    parser = new EmailParser();
  });

  describe("parseEmail", () => {
    test("should parse simple email from string", async () => {
      const result = await parser.parseEmail(TEST_EMAIL_CONTENT);

      expect(result.email).toBeDefined();
      expect(result.email.id).toBeDefined();
      expect(result.email.subject).toBe("Test Email");
      expect(result.email.from).toBe("sender@example.com");
      expect(result.email.to).toContain("recipient@example.com");
      expect(result.email.text).toContain("This is a test email body");

      expect(result.metadata.hasText).toBe(true);
      expect(result.metadata.processingTime).toBeGreaterThan(0);
    });

    test("should parse email from Buffer", async () => {
      const buffer = Buffer.from(TEST_EMAIL_CONTENT);
      const result = await parser.parseEmail(buffer);

      expect(result.email.subject).toBe("Test Email");
      expect(result.email.from).toBe("sender@example.com");
    });

    test("should parse email with attachments", async () => {
      const result = await parser.parseEmail(TEST_EMAIL_WITH_ATTACHMENT);

      expect(result.email.subject).toBe("Test Email with Attachment");
      expect(result.metadata.attachmentCount).toBeGreaterThan(0);
      expect(result.email.attachments).toBeDefined();
      expect(result.email.attachments.length).toBeGreaterThan(0);
    });

    test("should handle malformed email gracefully", async () => {
      const malformedEmail = "This is not a valid email";

      const result = await parser.parseEmail(malformedEmail);

      // Should not throw, but may have empty fields
      expect(result).toBeDefined();
      expect(result.email).toBeDefined();
    });

    test("should respect parsing options", async () => {
      const result = await parser.parseEmail(TEST_EMAIL_CONTENT, {
        keepAttachments: false,
        maxAttachmentSize: 1000,
      });

      expect(result).toBeDefined();
      expect(result.email).toBeDefined();
    });
  });

  describe("validateEmail", () => {
    test("should validate correct email structure", async () => {
      const result = await parser.parseEmail(TEST_EMAIL_CONTENT);
      const validation = parser.validateEmail(result.email);

      expect(validation.isValid).toBe(true);
      expect(validation.errors).toHaveLength(0);
    });

    test("should detect invalid email structure", () => {
      const invalidEmail = {
        id: "",
        subject: "",
        from: "",
        to: [],
        headers: {},
        text: "",
        attachments: [],
      };

      const validation = parser.validateEmail(invalidEmail);

      expect(validation.isValid).toBe(false);
      expect(validation.errors.length).toBeGreaterThan(0);
    });
  });
});
