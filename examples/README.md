# Email Transformer Examples

This directory contains example usage of the Email Transformer library.

## Examples

### 1. Basic Usage (`basic.ts`)

- Simple transformer setup
- Development server for testing
- Core configuration options

Run: `npm run dev` or `npx ts-node examples/basic.ts`

### 2. Python Extractor Integration (`with-python-extractor.ts`)

- Using the Python sidecar for advanced processing
- Order confirmation and invoice extraction examples
- Error handling and service availability checking

Run: `npx ts-node examples/with-python-extractor.ts`

### 3. Configuration Options (`config-options.ts`)

- Different configuration setups
- LLM provider examples (OpenAI, Ollama)
- Runtime configuration updates

Run: `npx ts-node examples/config-options.ts`

## Prerequisites

### For Basic Examples

```bash
npm install
npm run build
```

### For Python Extractor Examples

```bash
# Build and start the Python extractor service
npm run extractor:build
npm run extractor:start

# Verify it's running
curl http://localhost:8000/healthz
# Should return: {"status":"healthy"}
```

### For LLM Examples

Set up your API keys:

```bash
export OPENAI_API_KEY="your-key-here"
# or for Ollama, ensure it's running on localhost:11434
```

## Sample Data

The examples include sample email content for:

- Amazon order confirmations
- Invoice notifications
- Generic business emails

## Development

To create your own examples:

1. Import the library: `import { EmailTransformer } from '../src';`
2. Create a transformer instance with your config
3. Call `transformer.transform(emailContent)` when implementation is ready

Note: The actual transformation methods are not yet implemented - these examples show the API structure and configuration options.
