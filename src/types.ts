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

// Domain-specific interfaces derived from JSON schemas
export interface Address {
  name?: string;
  street?: string;
  city?: string;
  state?: string;
  postalCode?: string;
  country?: string;
}

export interface OrderData {
  orderId: string;
  orderNumber?: string;
  orderDate?: string;
  vendor?: string;
  customer?: {
    name?: string;
    email?: string;
  };
  items: Array<{
    sku?: string;
    name: string;
    description?: string;
    price: number;
    quantity: number;
    total?: number;
  }>;
  billingAddress?: Address;
  shippingAddress?: Address;
  subtotal?: number;
  tax?: number;
  shipping?: number;
  discount?: number;
  total: number;
  currency?: string;
  status?: 'confirmed' | 'processing' | 'shipped' | 'delivered' | 'cancelled';
  trackingNumber?: string;
  expectedDeliveryDate?: string;
}

export interface InvoiceData {
  invoiceNumber: string;
  invoiceId?: string;
  issueDate: string;
  dueDate?: string;
  vendor: {
    name: string;
    address?: Address;
    email?: string;
    phone?: string;
    taxId?: string;
  };
  customer: {
    name: string;
    address?: Address;
    email?: string;
    phone?: string;
  };
  lineItems: Array<{
    description: string;
    quantity?: number;
    unitPrice?: number;
    total: number;
    taxRate?: number;
  }>;
  subtotal?: number;
  tax?: number;
  discount?: number;
  total: number;
  currency?: string;
  status?: 'draft' | 'sent' | 'paid' | 'overdue' | 'cancelled';
  paymentTerms?: string;
  notes?: string;
}

export interface BookingData {
  bookingId: string;
  confirmationNumber?: string;
  provider?: string;
  bookingDate?: string;
  propertyName?: string;
  propertyType?: 'hotel' | 'apartment' | 'house' | 'room' | 'resort' | 'hostel' | 'other';
  address?: Address;
  guest?: {
    name?: string;
    email?: string;
    phone?: string;
  };
  checkInDate: string;
  checkOutDate: string;
  checkInTime?: string;
  checkOutTime?: string;
  nights?: number;
  guests?: {
    adults?: number;
    children?: number;
    total?: number;
  };
  rooms?: Array<{
    type?: string;
    description?: string;
    quantity?: number;
    rate?: number;
  }>;
  pricing?: {
    roomRate?: number;
    taxes?: number;
    fees?: number;
    discount?: number;
    total?: number;
  };
  currency?: string;
  status?: 'confirmed' | 'pending' | 'cancelled' | 'completed';
  cancellationPolicy?: string;
  specialRequests?: string;
}

export interface SignatureRequestData {
  envelopeId: string;
  requestId?: string;
  provider?: string;
  requestDate?: string;
  documentTitle: string;
  documentDescription?: string;
  sender?: {
    name?: string;
    email: string;
    company?: string;
  };
  signers: Array<{
    name?: string;
    email: string;
    role?: string;
    status: 'pending' | 'signed' | 'declined' | 'delivered' | 'completed';
    signedDate?: string;
    order?: number;
  }>;
  status: 'sent' | 'pending' | 'partially_signed' | 'completed' | 'declined' | 'cancelled' | 'expired';
  deadline?: string;
  expiryDate?: string;
  documentList?: Array<{
    name: string;
    pageCount?: number;
    size?: number;
  }>;
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  message?: string;
  securitySettings?: {
    accessCode?: boolean;
    phoneAuthentication?: boolean;
    idVerification?: boolean;
  };
}

export interface AlertData {
  alertId: string;
  incidentId?: string;
  source?: string;
  monitor?: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  priority?: 'p1' | 'p2' | 'p3' | 'p4' | 'p5';
  status?: 'triggered' | 'acknowledged' | 'resolved' | 'suppressed';
  component?: string;
  environment?: 'production' | 'staging' | 'development' | 'test';
  eventTime: string;
  detectedTime?: string;
  resolvedTime?: string;
  message: string;
  details?: string;
  actionRequired?: boolean;
  assignee?: {
    name?: string;
    email?: string;
    team?: string;
  };
  escalationPolicy?: string;
  tags?: string[];
  metrics?: {
    threshold?: number;
    currentValue?: number;
    unit?: string;
  };
  link?: string;
  runbook?: string;
  affectedHosts?: string[];
}

export interface SupportFollowupData {
  ticketId: string;
  ticketNumber?: string;
  provider?: string;
  subject: string;
  description?: string;
  status: 'open' | 'pending' | 'in_progress' | 'resolved' | 'closed' | 'on_hold';
  priority?: 'low' | 'normal' | 'high' | 'urgent' | 'critical';
  category?: string;
  customer?: {
    name?: string;
    email: string;
    company?: string;
    phone?: string;
    customerId?: string;
  };
  assignee?: {
    name?: string;
    email?: string;
    team?: string;
    role?: string;
  };
  createdTime?: string;
  lastUpdateTime?: string;
  responseTime?: {
    firstResponse?: string;
    nextResponse?: string;
    slaDeadline?: string;
  };
  resolution?: {
    summary?: string;
    resolution?: string;
    resolvedBy?: string;
    resolvedTime?: string;
    resolutionTime?: number;
  };
  nextAction?: string;
  actionBy?: 'customer' | 'agent' | 'system' | 'vendor';
  dueDate?: string;
  threadSummary?: string;
  lastMessage?: {
    from?: string;
    content?: string;
    timestamp?: string;
    type?: 'note' | 'public_reply' | 'private_note' | 'system';
  };
  tags?: string[];
  satisfactionRating?: {
    score?: number;
    comment?: string;
    submittedTime?: string;
  };
}

export interface GenericMessageData {
  messageId?: string;
  subject: string;
  from: {
    name?: string;
    email: string;
    domain?: string;
  };
  to?: Array<{
    name?: string;
    email: string;
  }>;
  date?: string;
  classification: {
    category: 'transactional' | 'promotional' | 'notification' | 'newsletter' | 'personal' | 'automated' | 'receipt' | 'reminder' | 'announcement' | 'other';
    intent: 'informational' | 'action_required' | 'confirmation' | 'request' | 'update' | 'marketing' | 'social' | 'security' | 'other';
    confidence?: number;
  };
  bodySummary?: string;
  keyPhrases?: string[];
  detectedEntities?: Array<{
    text: string;
    type: 'person' | 'organization' | 'location' | 'date' | 'time' | 'money' | 'phone' | 'email' | 'url' | 'product' | 'event' | 'other';
    confidence?: number;
  }>;
  actionItems?: Array<{
    action: string;
    dueDate?: string;
    priority?: 'low' | 'medium' | 'high';
    assignee?: string;
  }>;
  sentiment?: {
    polarity: 'positive' | 'neutral' | 'negative';
    score?: number;
    confidence?: number;
  };
  language?: string;
  hasAttachments?: boolean;
  attachmentTypes?: string[];
  isAutomated?: boolean;
  spamScore?: number;
}

// Union type for all domain data types
export type DomainData = 
  | OrderData 
  | InvoiceData 
  | BookingData 
  | SignatureRequestData 
  | AlertData 
  | SupportFollowupData 
  | GenericMessageData;