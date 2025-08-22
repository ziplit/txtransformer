# Email Extractor - Python Sidecar

Python service for extracting structured data from emails and attachments.

## Setup

```bash
pip install -r requirements.txt
python src/main.py
```

## API Endpoints

- `GET /healthz` - Health check
- `GET /readyz` - Readiness check
- `POST /extract` - Extract data from email (TODO)
