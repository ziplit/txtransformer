"""
Email Extractor - Python sidecar for processing emails and attachments
"""

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Email Extractor", version="0.1.0")

@app.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/readyz")
async def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready"}

@app.post("/extract")
async def extract_email():
    """Extract structured data from email"""
    return {"message": "Extraction endpoint - coming soon"}

def main():
    """Main entry point"""
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()