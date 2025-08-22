/**
 * Schema validation utilities
 */

import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import * as fs from 'fs-extra';
import * as path from 'path';

// Import JSON schemas
import emailCanonicalSchema from '../schemas/email-canonical.json';
import metaSchemaDescriptor from '../schemas/meta-schema-descriptor.v1.json';
import orderSchema from '../schemas/order.v1.json';
import invoiceSchema from '../schemas/invoice.v1.json';
import bookingSchema from '../schemas/booking.v1.json';
import signatureRequestSchema from '../schemas/signature_request.v1.json';
import alertSchema from '../schemas/alert.v1.json';
import supportFollowupSchema from '../schemas/support_followup.v1.json';
import genericMessageSchema from '../schemas/generic_message.v1.json';

export interface ValidationResult {
  valid: boolean;
  errors?: any[];
  schemaId?: string;
}

export class SchemaValidator {
  private ajv: Ajv;
  private schemas: Map<string, any> = new Map();

  constructor() {
    this.ajv = new Ajv({ 
      allErrors: true,
      verbose: true,
      strict: false
    });
    
    // Add format support (date, email, uri, etc.)
    addFormats(this.ajv);
    
    this.loadSchemas();
  }

  private loadSchemas(): void {
    // Load all domain schemas
    const schemaDefinitions = [
      { id: 'email-canonical', schema: emailCanonicalSchema },
      { id: 'meta-schema-descriptor', schema: metaSchemaDescriptor },
      { id: 'order', schema: orderSchema },
      { id: 'invoice', schema: invoiceSchema },
      { id: 'booking', schema: bookingSchema },
      { id: 'signature-request', schema: signatureRequestSchema },
      { id: 'alert', schema: alertSchema },
      { id: 'support-followup', schema: supportFollowupSchema },
      { id: 'generic-message', schema: genericMessageSchema }
    ];

    for (const { id, schema } of schemaDefinitions) {
      try {
        this.ajv.addSchema(schema, id);
        this.schemas.set(id, schema);
        
        // Also register by $id if present
        if (schema.$id) {
          this.schemas.set(schema.$id, schema);
        }
      } catch (error) {
        console.warn(`Failed to load schema ${id}:`, error);
      }
    }
  }

  /**
   * Validate data against a specific schema
   */
  validate(data: any, schemaId: string): ValidationResult {
    try {
      const validator = this.ajv.getSchema(schemaId);
      if (!validator) {
        return {
          valid: false,
          errors: [{ message: `Schema '${schemaId}' not found` }],
          schemaId
        };
      }

      const valid = validator(data) as boolean;
      return {
        valid,
        errors: valid ? undefined : (validator.errors || []),
        schemaId
      };
    } catch (error) {
      return {
        valid: false,
        errors: [{ message: `Validation error: ${error}` }],
        schemaId
      };
    }
  }

  /**
   * Validate email canonical format
   */
  validateEmailCanonical(data: any): ValidationResult {
    return this.validate(data, 'email-canonical');
  }

  /**
   * Try to validate against multiple domain schemas and return the best match
   */
  validateAgainstDomainSchemas(data: any): ValidationResult & { detectedDomain?: string } {
    const domainSchemas = ['order', 'invoice', 'booking', 'signature-request', 'alert', 'support-followup'];
    
    let bestMatch: ValidationResult & { detectedDomain?: string } = {
      valid: false,
      errors: [{ message: 'No matching schema found' }]
    };
    
    let highestScore = 0;

    for (const schemaId of domainSchemas) {
      const result = this.validate(data, schemaId);
      
      if (result.valid) {
        return {
          ...result,
          detectedDomain: schemaId
        };
      }

      // Score based on how many fields matched (fewer errors = better match)
      const score = this.calculateMatchScore(result.errors || []);
      if (score > highestScore) {
        highestScore = score;
        bestMatch = {
          ...result,
          detectedDomain: schemaId
        };
      }
    }

    // If no exact match, try generic schema
    const genericResult = this.validate(data, 'generic-message');
    if (genericResult.valid || highestScore === 0) {
      return {
        ...genericResult,
        detectedDomain: 'generic'
      };
    }

    return bestMatch;
  }

  /**
   * Calculate a match score based on validation errors
   */
  private calculateMatchScore(errors: any[]): number {
    if (!errors || errors.length === 0) return 100;
    
    // Simple scoring: fewer errors = higher score
    // Missing required fields count more than type mismatches
    let score = 100;
    
    for (const error of errors) {
      if (error.keyword === 'required') {
        score -= 20; // Missing required field is worse
      } else if (error.keyword === 'type') {
        score -= 10; // Type mismatch is less severe
      } else {
        score -= 5; // Other errors
      }
    }
    
    return Math.max(0, score);
  }

  /**
   * Get available schema IDs
   */
  getAvailableSchemas(): string[] {
    return Array.from(this.schemas.keys());
  }

  /**
   * Get schema definition by ID
   */
  getSchema(schemaId: string): any {
    return this.schemas.get(schemaId);
  }

  /**
   * Validate and suggest schema improvements
   */
  validateWithSuggestions(data: any, schemaId: string): ValidationResult & { suggestions?: string[] } {
    const result = this.validate(data, schemaId);
    
    if (result.valid) {
      return result;
    }

    const suggestions: string[] = [];
    
    if (result.errors) {
      for (const error of result.errors) {
        if (error.keyword === 'required') {
          suggestions.push(`Add required field: ${error.params?.missingProperty}`);
        } else if (error.keyword === 'type') {
          suggestions.push(`Field '${error.instancePath}' should be of type '${error.params?.type}'`);
        } else if (error.keyword === 'format') {
          suggestions.push(`Field '${error.instancePath}' should match format '${error.params?.format}'`);
        }
      }
    }

    return {
      ...result,
      suggestions
    };
  }
}

// Export singleton instance
export const schemaValidator = new SchemaValidator();