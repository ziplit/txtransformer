export const EMAIL_CANONICAL_SCHEMA = {
  type: "object",
  properties: {
    id: { type: "string" },
    subject: { type: "string" },
    from: { type: "string" },
    to: { type: "array", items: { type: "string" } },
    cc: { type: "array", items: { type: "string" } },
    headers: { type: "object" },
    text: { type: "string" },
    html: { type: "string" },
    attachments: {
      type: "array",
      items: {
        type: "object",
        properties: {
          filename: { type: "string" },
          contentType: { type: "string" },
          size: { type: "integer" },
          localPath: { type: "string" },
        },
        required: ["contentType", "size"],
      },
    },
  },
  required: ["id", "subject", "from", "to", "text", "attachments"],
} as const;

export const META_SCHEMA_DESCRIPTOR = {
  $id: "urn:meta:schema-descriptor:v1",
  type: "object",
  properties: {
    id: { type: "string" },
    title: { type: "string" },
    domain: { type: "string" },
    version: { type: "string", pattern: "^v\\d+(?:\\.\\d+)?$" },
    properties: { type: "object" },
    required: { type: "array", items: { type: "string" } },
    vendor_tags: { type: "array", items: { type: "string" } },
    examples: { type: "array" },
  },
  required: ["id", "title", "domain", "version", "properties", "required"],
} as const;

export const ORDER_SCHEMA = {
  id: "urn:schema:order:v1",
  title: "Order Confirmation",
  domain: "order",
  version: "v1",
  vendor_tags: ["amazon", "mercado_livre", "shopify"],
  properties: {
    orderId: { type: "string" },
    items: {
      type: "array",
      items: {
        type: "object",
        properties: {
          sku: { type: "string" },
          name: { type: "string" },
          price: { type: "number" },
          quantity: { type: "integer" },
        },
      },
    },
    billingAddress: { type: "object" },
    shippingAddress: { type: "object" },
    price: { type: "number" },
    currency: { type: "string" },
    expectedDeliveryDate: { type: "string", format: "date" },
  },
  required: ["orderId", "items"],
} as const;

export const INVOICE_SCHEMA = {
  id: "urn:schema:invoice:v1",
  title: "Invoice",
  domain: "invoice",
  version: "v1",
  properties: {
    invoiceNumber: { type: "string" },
    issueDate: { type: "string", format: "date" },
    dueDate: { type: "string", format: "date" },
    vendor: { type: "string" },
    customer: { type: "string" },
    lineItems: {
      type: "array",
      items: {
        type: "object",
        properties: {
          description: { type: "string" },
          quantity: { type: "integer" },
          unitPrice: { type: "number" },
          total: { type: "number" },
        },
      },
    },
    subtotal: { type: "number" },
    tax: { type: "number" },
    total: { type: "number" },
    currency: { type: "string" },
  },
  required: ["invoiceNumber", "total"],
} as const;

export const BOOKING_SCHEMA = {
  id: "urn:schema:booking:v1",
  title: "Booking Confirmation",
  domain: "booking",
  version: "v1",
  vendor_tags: ["airbnb", "booking.com"],
  properties: {
    bookingId: { type: "string" },
    provider: { type: "string" },
    propertyName: { type: "string" },
    address: { type: "object" },
    guestName: { type: "string" },
    checkInDate: { type: "string", format: "date" },
    checkOutDate: { type: "string", format: "date" },
    guestsCount: { type: "integer" },
    price: { type: "number" },
    currency: { type: "string" },
  },
  required: ["bookingId", "checkInDate", "checkOutDate"],
} as const;

export const SIGNATURE_REQUEST_SCHEMA = {
  id: "urn:schema:signature_request:v1",
  title: "Signature Request",
  domain: "signature_request",
  version: "v1",
  vendor_tags: ["docusign", "adobesign"],
  properties: {
    envelopeId: { type: "string" },
    provider: { type: "string" },
    documentTitle: { type: "string" },
    signers: {
      type: "array",
      items: {
        type: "object",
        properties: {
          name: { type: "string" },
          email: { type: "string" },
          status: { type: "string" },
        },
      },
    },
    status: { type: "string" },
    deadline: { type: "string", format: "date" },
    documentList: { type: "array", items: { type: "string" } },
  },
  required: ["envelopeId", "status"],
} as const;

export const ALERT_SCHEMA = {
  id: "urn:schema:alert:v1",
  title: "System Alert",
  domain: "alert",
  version: "v1",
  properties: {
    alertId: { type: "string" },
    source: { type: "string" },
    severity: { type: "string" },
    component: { type: "string" },
    eventTime: { type: "string", format: "date-time" },
    message: { type: "string" },
    actionRequired: { type: "boolean" },
    link: { type: "string" },
  },
  required: ["severity", "message"],
} as const;

export const SUPPORT_FOLLOWUP_SCHEMA = {
  id: "urn:schema:support_followup:v1",
  title: "Support Follow-up",
  domain: "support_followup",
  version: "v1",
  properties: {
    ticketId: { type: "string" },
    provider: { type: "string" },
    subject: { type: "string" },
    status: { type: "string" },
    assignee: { type: "string" },
    lastUpdateTime: { type: "string", format: "date-time" },
    nextAction: { type: "string" },
    threadSummary: { type: "string" },
  },
  required: ["ticketId", "subject"],
} as const;

export const GENERIC_MESSAGE_SCHEMA = {
  id: "urn:schema:generic_message:v1",
  title: "Generic Message",
  domain: "generic",
  version: "v1",
  properties: {
    subject: { type: "string" },
    from: { type: "string" },
    to: { type: "array", items: { type: "string" } },
    date: { type: "string" },
    bodySummary: { type: "string" },
    detectedEntities: { type: "array", items: { type: "string" } },
  },
  required: ["subject"],
} as const;

// Export all schemas for easy access
export const DOMAIN_SCHEMAS = {
  order: ORDER_SCHEMA,
  invoice: INVOICE_SCHEMA,
  booking: BOOKING_SCHEMA,
  signature_request: SIGNATURE_REQUEST_SCHEMA,
  alert: ALERT_SCHEMA,
  support_followup: SUPPORT_FOLLOWUP_SCHEMA,
  generic: GENERIC_MESSAGE_SCHEMA,
} as const;
