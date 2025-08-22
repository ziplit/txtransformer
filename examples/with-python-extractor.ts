import { EmailTransformer } from '../src';
import * as fs from 'fs-extra';

async function exampleWithExtractor() {
  console.log('Email Transformer with Python Extractor - Example');

  // Create transformer with Python extractor
  const transformer = new EmailTransformer({
    pythonExtractorUrl: 'http://localhost:8000',
    tempDir: './temp',
    enableCaching: true,
    timeout: 60000
  });

  // Sample email with order confirmation
  const orderEmail = `
    From: noreply@amazon.com
    To: customer@example.com
    Subject: Your Amazon.com order #123-4567890 has shipped
    Date: Thu, 22 Aug 2024 10:30:00 +0000

    Dear Customer,

    Good news! Your order has shipped and is on its way.

    Order Details:
    Order Number: 123-4567890
    Items:
    - Wireless Bluetooth Headphones - $99.99 (Qty: 1)
    - USB-C Cable 6ft - $12.99 (Qty: 2)
    
    Subtotal: $125.97
    Tax: $10.08
    Total: $136.05

    Shipping Address:
    John Doe
    123 Main Street
    Anytown, CA 90210

    Tracking Number: 1Z999AA1234567890
    Expected Delivery: August 25, 2024

    Thank you for your order!
  `;

  // Sample invoice email
  const invoiceEmail = `
    From: billing@acme-corp.com
    To: accounts@company.com
    Subject: Invoice #INV-2024-001 - Due August 30, 2024

    Invoice Details:
    Invoice Number: INV-2024-001
    Issue Date: August 15, 2024
    Due Date: August 30, 2024

    Bill To:
    ABC Company Inc.
    456 Business Ave
    Corporate City, NY 10001

    Services:
    - Web Development Services (40 hours) - $150/hr = $6,000.00
    - Monthly Hosting - $99.00

    Subtotal: $6,099.00
    Tax (8.5%): $518.42
    Total: $6,617.42

    Payment Terms: Net 15 days
  `;

  try {
    console.log('Processing order confirmation email...');
    // TODO: Uncomment when implementation is ready
    // const orderResult = await transformer.transform(orderEmail);
    // console.log('Order extraction result:', {
    //   schemaType: orderResult.schemaType,
    //   confidence: orderResult.confidence,
    //   orderId: orderResult.data.orderId,
    //   total: orderResult.data.price,
    //   itemCount: orderResult.data.items?.length
    // });

    console.log('Processing invoice email...');
    // TODO: Uncomment when implementation is ready
    // const invoiceResult = await transformer.transform(invoiceEmail);
    // console.log('Invoice extraction result:', {
    //   schemaType: invoiceResult.schemaType,
    //   confidence: invoiceResult.confidence,
    //   invoiceNumber: invoiceResult.data.invoiceNumber,
    //   total: invoiceResult.data.total,
    //   dueDate: invoiceResult.data.dueDate
    // });

    console.log('Example completed! Ready for implementation.');

  } catch (error) {
    console.error('Error processing emails:', error);
  }
}

// Check if Python extractor is available
async function checkExtractor() {
  try {
    const response = await fetch('http://localhost:8000/healthz');
    return response.ok;
  } catch {
    return false;
  }
}

async function main() {
  const extractorAvailable = await checkExtractor();
  
  if (!extractorAvailable) {
    console.log('Python extractor not available. Start it with:');
    console.log('npm run extractor:build && npm run extractor:start');
    console.log('Running example without extractor...');
  }

  await exampleWithExtractor();
}

if (require.main === module) {
  main();
}