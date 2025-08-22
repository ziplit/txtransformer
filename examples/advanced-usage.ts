import {
  EmailTransformer,
  createLogger,
  TransformerError,
  EventUtils,
} from "../src";

async function advancedExample() {
  // Create a custom logger
  const logger = createLogger({
    level: "debug",
    pretty: true,
    name: "email-transformer-example",
  });

  // Create transformer with custom logger
  const transformer = new EmailTransformer(
    {
      tempDir: "./temp-example",
      enableCaching: true,
      timeout: 30000,
    },
    {
      level: "debug",
      pretty: true,
      name: "transformer",
    },
  );

  // Set up event listeners
  transformer.on("transformation:started", (data) => {
    logger.info(`🚀 Started processing email: ${data.email.subject}`);
  });

  transformer.on("progress", (data) => {
    logger.info(`⏳ Progress: ${data.stage} - ${data.progress}%`);
  });

  transformer.on("email:parsed", (data) => {
    logger.info(
      `📧 Parsed email from ${data.email.from} with ${data.metadata.attachmentCount} attachments`,
    );
  });

  transformer.on("attachments:processing-started", (data) => {
    logger.info(`📎 Processing ${data.count} attachments`);
  });

  transformer.on("attachment:blocked", (data) => {
    logger.warn(
      `🚫 Blocked attachment ${data.attachment.filename}: ${data.reason}`,
    );
  });

  transformer.on("cache:hit", (data) => {
    logger.info(`⚡ Cache hit for transformation ${data.id}`);
  });

  transformer.on("cache:miss", (data) => {
    logger.info(`💾 Cache miss for transformation ${data.id}`);
  });

  transformer.on("transformation:completed", (data) => {
    logger.info(
      `✅ Completed processing in ${data.duration}ms - Schema: ${data.result.schemaType}, Confidence: ${data.result.confidence}`,
    );
  });

  transformer.on("transformation:failed", (data) => {
    logger.error(
      `❌ Failed processing after ${data.duration}ms: ${data.error.message}`,
    );
  });

  // Sample email content
  const sampleEmail = `From: orders@example-store.com
To: customer@example.com
Subject: Order Confirmation #12345
Date: ${new Date().toISOString()}

Dear Customer,

Your order #12345 has been confirmed.

Order Details:
- Product: Example Product
- Quantity: 2
- Total: $49.98

Thank you for your business!
`;

  const sampleEmailWithAttachment = `From: sender@example.com
To: recipient@example.com
Subject: Document with Attachment
Date: ${new Date().toISOString()}
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

Please find the attached document.

--boundary123
Content-Type: application/pdf; name="document.pdf"
Content-Disposition: attachment; filename="document.pdf"

%PDF-1.4 fake pdf content
--boundary123--
`;

  try {
    logger.info("🔧 Starting advanced email transformation example");

    // Example 1: Basic transformation
    logger.info("\n--- Example 1: Basic Order Email ---");
    const result1 = await transformer.transform(sampleEmail);
    console.log("Result:", JSON.stringify(result1, null, 2));

    // Example 2: Email with attachments
    logger.info("\n--- Example 2: Email with Attachments ---");
    const result2 = await transformer.transform(sampleEmailWithAttachment);
    console.log("Result:", JSON.stringify(result2, null, 2));

    // Example 3: Cached transformation (should be faster)
    logger.info("\n--- Example 3: Cached Transformation ---");
    const result3 = await transformer.transform(sampleEmail);
    console.log(
      "Cached result processed in:",
      result3.metadata.processingTime,
      "ms",
    );

    // Example 4: Waiting for specific events
    logger.info("\n--- Example 4: Event-driven Processing ---");
    const transformationPromise = transformer.transform(`From: test@example.com
To: user@example.com
Subject: Test Event Processing
Date: ${new Date().toISOString()}

This is a test email for event processing.`);

    // Wait for parsing to complete
    const parseEvent = await EventUtils.waitForEvent(
      transformer,
      "email:parsed",
      5000,
    );
    logger.info(`📧 Email parsed: ${parseEvent.email.subject}`);

    // Wait for transformation to complete
    const result4 = await transformationPromise;
    console.log("Event-driven result:", JSON.stringify(result4, null, 2));

    // Example 5: Error handling
    logger.info("\n--- Example 5: Error Handling ---");
    try {
      await transformer.transform(null as any);
    } catch (error) {
      if (error instanceof TransformerError) {
        logger.error(
          `Caught TransformerError: ${error.message} (Code: ${error.code})`,
        );
      } else {
        logger.error("Caught unexpected error:", error);
      }
    }

    // Get statistics
    const stats = await transformer.getStats();
    logger.info("📊 Transformer Statistics:");
    console.log(JSON.stringify(stats, null, 2));
  } catch (error) {
    logger.error("Example failed:", error);
  } finally {
    // Cleanup
    await transformer.cleanup();
    logger.info("🧹 Cleanup completed");
  }
}

// Run the example
if (require.main === module) {
  advancedExample().catch(console.error);
}
