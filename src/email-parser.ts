import { simpleParser, ParsedMail, Attachment } from "mailparser";
import { EmailCanonical, AttachmentInfo } from "./types";
import * as crypto from "crypto";

export interface EmailParsingOptions {
  /** Whether to keep attachment content in memory */
  keepAttachments?: boolean;
  /** Maximum attachment size to keep in memory (bytes) */
  maxAttachmentSize?: number;
  /** Skip text extraction from HTML */
  skipTextExtraction?: boolean;
}

export interface EmailParsingResult {
  /** Parsed email in canonical format */
  email: EmailCanonical;
  /** Raw parsed mail object from mailparser */
  rawParsed: ParsedMail;
  /** Parsing metadata */
  metadata: {
    hasHtml: boolean;
    hasText: boolean;
    attachmentCount: number;
    totalSize: number;
    processingTime: number;
  };
}

/**
 * Email parser class using mailparser
 */
export class EmailParser {
  private options: Required<EmailParsingOptions>;

  constructor(options: EmailParsingOptions = {}) {
    this.options = {
      keepAttachments: true,
      maxAttachmentSize: 50 * 1024 * 1024, // 50MB
      skipTextExtraction: false,
      ...options,
    };
  }

  /**
   * Parse email from raw string or Buffer
   */
  async parseEmail(
    emailData: string | Buffer,
    options: EmailParsingOptions = {},
  ): Promise<EmailParsingResult> {
    const startTime = Date.now();
    const parseOptions = { ...this.options, ...options };

    try {
      // Parse email using mailparser - using basic options
      const parsed = await simpleParser(emailData);

      // Convert to canonical format
      const canonical = await this.convertToCanonical(parsed, parseOptions);

      const processingTime = Date.now() - startTime;

      return {
        email: canonical,
        rawParsed: parsed,
        metadata: {
          hasHtml: !!parsed.html,
          hasText: !!parsed.text,
          attachmentCount: parsed.attachments?.length || 0,
          totalSize: this.calculateTotalSize(parsed),
          processingTime,
        },
      };
    } catch (error) {
      throw new Error(
        `Email parsing failed: ${error instanceof Error ? error.message : "Unknown error"}`,
      );
    }
  }

  /**
   * Parse email from file path
   */
  async parseEmailFromFile(filePath: string): Promise<EmailParsingResult> {
    const fs = await import("fs-extra");
    const emailData = await fs.readFile(filePath);
    return this.parseEmail(emailData);
  }

  /**
   * Convert ParsedMail to EmailCanonical format
   */
  private async convertToCanonical(
    parsed: ParsedMail,
    options: Required<EmailParsingOptions>,
  ): Promise<EmailCanonical> {
    // Generate unique ID for the email
    const emailId = this.generateEmailId(parsed);

    // Extract sender information
    const fromAddress = this.extractFromAddress(parsed);

    // Extract recipient information
    const toAddresses = this.extractToAddresses(parsed);
    const ccAddresses = this.extractCcAddresses(parsed);

    // Process attachments
    const attachments = await this.processAttachments(
      parsed.attachments || [],
      options,
    );

    // Extract headers
    const headers = this.extractHeaders(parsed);

    // Get text content (prefer text, fallback to HTML conversion)
    const textContent = this.extractTextContent(parsed);

    return {
      id: emailId,
      subject: parsed.subject || "",
      from: fromAddress,
      to: toAddresses,
      cc: ccAddresses.length > 0 ? ccAddresses : undefined,
      headers,
      text: textContent,
      html: parsed.html || undefined,
      attachments,
    };
  }

  /**
   * Generate unique email ID
   */
  private generateEmailId(parsed: ParsedMail): string {
    // Try to use Message-ID header first
    if (parsed.messageId) {
      return parsed.messageId.replace(/[<>]/g, "");
    }

    // Generate hash from subject, from, date
    const hashInput = [
      parsed.subject || "",
      parsed.from?.text || "",
      parsed.date?.toISOString() || Date.now().toString(),
    ].join("|");

    return crypto
      .createHash("sha256")
      .update(hashInput)
      .digest("hex")
      .substring(0, 16);
  }

  /**
   * Extract sender address
   */
  private extractFromAddress(parsed: ParsedMail): string {
    if (parsed.from?.value && parsed.from.value.length > 0) {
      return parsed.from.value[0].address || "";
    }
    return parsed.from?.text || "";
  }

  /**
   * Extract recipient addresses
   */
  private extractToAddresses(parsed: ParsedMail): string[] {
    if (!parsed.to) return [];

    if (Array.isArray(parsed.to)) {
      return parsed.to
        .flatMap((addr) =>
          addr.value
            ? addr.value.map((v) => v.address || v.name || "")
            : [addr.text || ""],
        )
        .filter(Boolean);
    }

    if (parsed.to.value) {
      return parsed.to.value
        .map((v) => v.address || v.name || "")
        .filter(Boolean);
    }

    return [parsed.to.text || ""].filter(Boolean);
  }

  /**
   * Extract CC addresses
   */
  private extractCcAddresses(parsed: ParsedMail): string[] {
    if (!parsed.cc) return [];

    if (Array.isArray(parsed.cc)) {
      return parsed.cc
        .flatMap((addr) =>
          addr.value
            ? addr.value.map((v) => v.address || v.name || "")
            : [addr.text || ""],
        )
        .filter(Boolean);
    }

    if (parsed.cc.value) {
      return parsed.cc.value
        .map((v) => v.address || v.name || "")
        .filter(Boolean);
    }

    return [parsed.cc.text || ""].filter(Boolean);
  }

  /**
   * Extract headers as key-value pairs
   */
  private extractHeaders(parsed: ParsedMail): Record<string, string> {
    const headers: Record<string, string> = {};

    if (parsed.headers) {
      for (const [key, value] of parsed.headers) {
        if (typeof value === "string") {
          headers[key.toLowerCase()] = value;
        } else if (Array.isArray(value)) {
          headers[key.toLowerCase()] = value.join(", ");
        } else if (value) {
          headers[key.toLowerCase()] = String(value);
        }
      }
    }

    // Add standard headers
    if (parsed.date) {
      headers["date"] = parsed.date.toISOString();
    }
    if (parsed.messageId) {
      headers["message-id"] = parsed.messageId;
    }

    return headers;
  }

  /**
   * Extract text content from email
   */
  private extractTextContent(parsed: ParsedMail): string {
    if (parsed.text) {
      return parsed.text;
    }

    if (parsed.html && !this.options.skipTextExtraction) {
      // Basic HTML to text conversion (mailparser should handle this)
      return this.htmlToText(parsed.html);
    }

    return "";
  }

  /**
   * Process email attachments
   */
  private async processAttachments(
    attachments: Attachment[],
    options: Required<EmailParsingOptions>,
  ): Promise<AttachmentInfo[]> {
    const processedAttachments: AttachmentInfo[] = [];

    for (const attachment of attachments) {
      const attachmentInfo: AttachmentInfo = {
        filename: attachment.filename || undefined,
        contentType: attachment.contentType || "application/octet-stream",
        size: attachment.size || 0,
      };

      // Include content if within size limits and keeping attachments
      if (
        options.keepAttachments &&
        attachment.content &&
        attachment.size <= options.maxAttachmentSize
      ) {
        attachmentInfo.content = attachment.content;
      }

      processedAttachments.push(attachmentInfo);
    }

    return processedAttachments;
  }

  /**
   * Calculate total size of parsed email
   */
  private calculateTotalSize(parsed: ParsedMail): number {
    let totalSize = 0;

    // Add text content size
    if (parsed.text) {
      totalSize += Buffer.byteLength(parsed.text, "utf8");
    }

    // Add HTML content size
    if (parsed.html) {
      totalSize += Buffer.byteLength(parsed.html, "utf8");
    }

    // Add attachment sizes
    if (parsed.attachments) {
      for (const attachment of parsed.attachments) {
        totalSize += attachment.size || 0;
      }
    }

    return totalSize;
  }

  /**
   * Basic HTML to text conversion
   */
  private htmlToText(html: string): string {
    return html
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/p>/gi, "\n\n")
      .replace(/<[^>]*>/g, "")
      .replace(/&nbsp;/g, " ")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&")
      .replace(/\s+/g, " ")
      .trim();
  }

  /**
   * Validate email structure
   */
  validateEmail(email: EmailCanonical): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!email.id) {
      errors.push("Email ID is required");
    }

    if (!email.subject && !email.text && !email.html) {
      errors.push("Email must have subject or content");
    }

    if (!email.from) {
      errors.push("Email must have a sender");
    }

    if (!email.to || email.to.length === 0) {
      errors.push("Email must have at least one recipient");
    }

    return {
      isValid: errors.length === 0,
      errors,
    };
  }
}

// Export singleton instance for convenience
export const emailParser = new EmailParser();
