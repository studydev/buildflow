# BuildFlow Backend API

FastAPI backend for BuildFlow - Learning content management and GitHub analysis.

## Quick Start

### Prerequisites

- Python 3.12+
- Poetry

### Setup

```bash
# Install dependencies
poetry install

# Copy environment file
cp .env.example .env.local

# Run development server
poetry run uvicorn app.main:app --reload --port 8000
```

### Verify

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Expected response:
# {
#   "success": true,
#   "data": {"status": "healthy"},
#   "meta": {"timestamp": "...", "correlationId": "..."}
# }
```

### API Documentation

- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
- OpenAPI JSON: http://localhost:8000/api/v1/openapi.json

## Development

```bash
# Run linter
poetry run ruff check app

# Run tests
poetry run pytest
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py      # Package init
│   ├── main.py          # FastAPI app factory
│   └── config.py        # Settings from environment
├── tests/               # Test files
├── pyproject.toml       # Dependencies
└── README.md            # This file
```
