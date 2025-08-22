import { EmailTransformer } from "../src";
import { createServer } from "http";

async function example() {
  // Create transformer instance
  const transformer = new EmailTransformer({
    pythonExtractorUrl:
      process.env.PYTHON_EXTRACTOR_URL || "http://localhost:8000",
    tempDir: "./temp",
    enableCaching: true,
  });

  // Example email content
  const emailContent = `
    From: orders@amazon.com
    To: customer@example.com
    Subject: Your Amazon.com order has shipped

    Hello,

    Your order #123-4567890 has been shipped and is on its way to you.
    
    Order Details:
    - Product: Wireless Headphones
    - Price: $99.99
    - Quantity: 1
    
    Tracking: 1Z999AA1234567890
  `;

  try {
    console.log("Email Transformer Library - Example");
    console.log("Configuration:", transformer.getConfig());

    // TODO: Transform the email when implementation is ready
    // const result = await transformer.transform(emailContent);
    // console.log('Extraction Result:', JSON.stringify(result, null, 2));

    // Start a simple server for development
    const port = process.env.PORT || 3000;
    const server = createServer((req, res) => {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          status: "ready",
          library: "@ziplit/txtransformer",
          timestamp: new Date().toISOString(),
        }),
      );
    });

    server.listen(port, () => {
      console.log(`Example server running on port ${port}`);
      console.log("Library is ready for implementation!");
    });
  } catch (error) {
    console.error("Error:", error);
  }
}

if (require.main === module) {
  example();
}
