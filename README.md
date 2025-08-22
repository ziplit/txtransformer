# Email Transformer

A TypeScript library for extracting structured data from emails and attachments.

## Features

- 📧 Parse emails and extract structured data
- 🔍 Support for multiple document types (PDF, DOCX, images)
- 🤖 Optional AI/LLM integration for enhanced extraction
- 🐍 Optional Python sidecar for heavy processing (OCR, NLP)
- 📊 Confidence scoring and provenance tracking
- 🏗️ Configurable storage and processing options

## Installation

```bash
npm install @ziplit/txtransformer
```

## Quick Start

```typescript
import { EmailTransformer } from "@ziplit/txtransformer";

const transformer = new EmailTransformer({
  tempDir: "./temp",
  enableCaching: true,
});

// Transform email content
const result = await transformer.transform(emailContent);
console.log("Extracted data:", result.data);
console.log("Confidence:", result.confidence);
```

## With Python Extractor

For advanced document processing (OCR, table extraction, NLP), use the optional Python sidecar:

```bash
# Start the Python extractor service
npm run extractor:build
npm run extractor:start
```

```typescript
const transformer = new EmailTransformer({
  pythonExtractorUrl: "http://localhost:8000",
  tempDir: "./temp",
});

const result = await transformer.transform(emailContent);
```

## Configuration

```typescript
interface TransformerConfig {
  pythonExtractorUrl?: string; // Python service URL
  tempDir: string; // Temporary files directory
  enableCaching: boolean; // Enable file caching
  timeout: number; // Request timeout (ms)
  llm?: {
    // LLM configuration
    provider: "openai" | "anthropic" | "ollama" | "local";
    apiKey?: string;
    modelName?: string;
  };
}
```

## Supported Schema Types

The library can extract data for various document types:

- **Orders** - E-commerce order confirmations
- **Invoices** - Bills and invoices
- **Bookings** - Hotel/travel reservations
- **Signatures** - Document signing requests
- **Alerts** - System notifications
- **Support** - Customer support threads
- **Generic** - General message classification

## Development

```bash
# Install dependencies
npm install

# Build the library
npm run build

# Run examples
npm run dev

# Start Python extractor
npm run extractor:start
```
