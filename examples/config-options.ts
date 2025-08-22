import { EmailTransformer } from '../src';
import { TransformerConfig } from '../src/types';

function basicConfig(): TransformerConfig {
  return {
    tempDir: './temp',
    enableCaching: true,
    timeout: 30000
  };
}

function advancedConfig(): TransformerConfig {
  return {
    pythonExtractorUrl: 'http://localhost:8000',
    tempDir: './temp',
    enableCaching: true,
    timeout: 60000,
    llm: {
      provider: 'openai',
      apiKey: process.env.OPENAI_API_KEY,
      modelName: 'gpt-4'
    },
    storage: {
      type: 'filesystem'
    }
  };
}

function ollamaConfig(): TransformerConfig {
  return {
    tempDir: './temp',
    enableCaching: true,
    timeout: 45000,
    llm: {
      provider: 'ollama',
      baseUrl: 'http://localhost:11434',
      modelName: 'llama2'
    }
  };
}

async function demonstrateConfigurations() {
  console.log('Email Transformer Configuration Examples');

  // Basic configuration (no external services)
  console.log('1. Basic Configuration (Local processing only):');
  const basic = new EmailTransformer(basicConfig());
  console.log(JSON.stringify(basic.getConfig(), null, 2));

  // Advanced configuration with OpenAI
  console.log('2. Advanced Configuration (Python + OpenAI):');
  const advanced = new EmailTransformer(advancedConfig());
  console.log(JSON.stringify(advanced.getConfig(), null, 2));

  // Ollama configuration for local LLM
  console.log('3. Ollama Configuration (Local LLM):');
  const ollama = new EmailTransformer(ollamaConfig());
  console.log(JSON.stringify(ollama.getConfig(), null, 2));

  // Runtime configuration changes
  console.log('4. Runtime Configuration Update:');
  basic.configure({
    timeout: 60000,
    pythonExtractorUrl: 'http://localhost:8000'
  });
  console.log('Updated config:', JSON.stringify(basic.getConfig(), null, 2));

  console.log('Configuration examples complete!');
}

if (require.main === module) {
  demonstrateConfigurations();
}