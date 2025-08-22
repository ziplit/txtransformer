/**
 * Schema loading utilities
 */

import * as path from "path";
import * as fs from "fs-extra";

export interface SchemaInfo {
  id: string;
  title: string;
  domain: string;
  version: string;
  schema: any;
}

export class SchemaLoader {
  private schemasPath: string;
  private loadedSchemas: Map<string, SchemaInfo> = new Map();

  constructor(schemasPath?: string) {
    this.schemasPath = schemasPath || path.join(__dirname, "..", "schemas");
  }

  /**
   * Load all schemas from the schemas directory
   */
  async loadAllSchemas(): Promise<SchemaInfo[]> {
    const schemaFiles = [
      "email-canonical.json",
      "order.v1.json",
      "invoice.v1.json",
      "booking.v1.json",
      "signature_request.v1.json",
      "alert.v1.json",
      "support_followup.v1.json",
      "generic_message.v1.json",
    ];

    const schemas: SchemaInfo[] = [];

    for (const filename of schemaFiles) {
      try {
        const schemaPath = path.join(this.schemasPath, filename);
        const schemaContent = await fs.readJSON(schemaPath);

        const schemaInfo: SchemaInfo = {
          id: schemaContent.$id || path.basename(filename, ".json"),
          title: schemaContent.title || filename,
          domain: schemaContent.domain || "unknown",
          version: schemaContent.version || "v1",
          schema: schemaContent,
        };

        this.loadedSchemas.set(schemaInfo.id, schemaInfo);
        schemas.push(schemaInfo);
      } catch (error) {
        console.warn(`Failed to load schema ${filename}:`, error);
      }
    }

    return schemas;
  }

  /**
   * Get schema by ID
   */
  getSchema(id: string): SchemaInfo | undefined {
    return this.loadedSchemas.get(id);
  }

  /**
   * Get all loaded schemas
   */
  getAllSchemas(): SchemaInfo[] {
    return Array.from(this.loadedSchemas.values());
  }

  /**
   * Get schemas by domain
   */
  getSchemasByDomain(domain: string): SchemaInfo[] {
    return Array.from(this.loadedSchemas.values()).filter(
      (schema) => schema.domain === domain,
    );
  }

  /**
   * Get domain schemas (excluding meta schemas)
   */
  getDomainSchemas(): SchemaInfo[] {
    const domainTypes = [
      "order",
      "invoice",
      "booking",
      "signature_request",
      "alert",
      "support_followup",
      "generic",
    ];
    return Array.from(this.loadedSchemas.values()).filter((schema) =>
      domainTypes.includes(schema.domain),
    );
  }
}

// Export singleton instance
export const schemaLoader = new SchemaLoader();
