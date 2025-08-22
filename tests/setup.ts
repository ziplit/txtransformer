import * as fs from "fs-extra";
import * as path from "path";

// Create test temp directory
const testTempDir = path.join(__dirname, "../temp-test");

beforeAll(async () => {
  await fs.ensureDir(testTempDir);
});

afterAll(async () => {
  // Clean up test temp directory
  try {
    await fs.remove(testTempDir);
  } catch (error) {
    // Ignore cleanup errors
  }
});

// Export test helpers
export const TEST_TEMP_DIR = testTempDir;
export const TEST_EMAIL_CONTENT = `From: sender@example.com
To: recipient@example.com
Subject: Test Email
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test@example.com>

This is a test email body.
`;

export const TEST_EMAIL_WITH_ATTACHMENT = `From: sender@example.com
To: recipient@example.com
Subject: Test Email with Attachment
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test-attachment@example.com>
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

This is the email body.

--boundary123
Content-Type: text/plain; name="test.txt"
Content-Disposition: attachment; filename="test.txt"

Test attachment content
--boundary123--
`;
