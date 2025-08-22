export interface TransformerConfig {
  /** URL of the Python extractor service (optional) */
  pythonExtractorUrl?: string;
  
  /** Directory for temporary files */
  tempDir: string;
  
  /** Enable file content caching */
  enableCaching: boolean;
  
  /** Request timeout in milliseconds */
  timeout: number;
  
  /** LLM provider configuration */
  llm?: {
    provider: 'openai' | 'anthropic' | 'ollama' | 'local';
    apiKey?: string;
    modelName?: string;
    baseUrl?: string;
  };
  
  /** Storage adapter configuration */
  storage?: {
    type: 'filesystem' | 'memory' | 'custom';
    adapter?: StorageAdapter;
  };
}

export interface ExtractionResult {
  /** Unique ID for this extraction */
  id: string;
  
  /** Detected schema type */
  schemaType: string;
  
  /** Extracted structured data */
  data: Record<string, any>;
  
  /** Overall confidence score (0-1) */
  confidence: number;
  
  /** Provenance information */
  provenance: ProvenanceInfo;
  
  /** Processing metadata */
  metadata: {
    processingTime: number;
    extractorVersion: string;
    timestamp: string;
  };
}

export interface ProvenanceInfo {
  /** Source of each extracted field */
  fieldSources: Record<string, FieldProvenance>;
  
  /** Extraction method used */
  extractionMethods: string[];
  
  /** Confidence breakdown by method */
  methodConfidence: Record<string, number>;
}

export interface FieldProvenance {
  /** Extraction method that provided this field */
  method: 'regex' | 'nlp' | 'llm' | 'table' | 'ocr';
  
  /** Confidence score for this field */
  confidence: number;
  
  /** Evidence supporting this extraction */
  evidence: string;
  
  /** Source location (e.g., email body, attachment) */
  sourceLocation: string;
}

export interface EmailCanonical {
  id: string;
  subject: string;
  from: string;
  to: string[];
  cc?: string[];
  headers: Record<string, string>;
  text: string;
  html?: string;
  attachments: AttachmentInfo[];
}

export interface AttachmentInfo {
  filename?: string;
  contentType: string;
  size: number;
  content?: Buffer;
  localPath?: string;
}

export interface StorageAdapter {
  store(key: string, data: Buffer): Promise<string>;
  retrieve(key: string): Promise<Buffer>;
  delete(key: string): Promise<void>;
  exists(key: string): Promise<boolean>;
}

export interface ExtractorCandidates {
  /** Task/email ID */
  id: string;
  
  /** Extracted field candidates */
  candidates: Record<string, FieldCandidate[]>;
  
  /** Processing metadata */
  metadata: {
    processingTime: number;
    methods: string[];
  };
}

export interface FieldCandidate {
  /** Field name */
  field: string;
  
  /** Extracted value */
  value: any;
  
  /** Confidence score */
  confidence: number;
  
  /** Extraction method */
  method: string;
  
  /** Supporting evidence */
  evidence: string;
}