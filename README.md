# trip-collab-ai

Independent FastAPI AI service for Trip-Collab.

This repo is Phase 0 only: a minimal runnable service skeleton with mock AI responses. It does not call OpenRouter, does not connect to a database, and does not write any Trip-Collab data.

## Purpose

`trip-collab-ai` owns LLM provider integration, prompts, schema validation, fallback behavior, and AI-specific response shaping for Trip-Collab.

The main systems remain separate:

- `trip-collab-web`: Vue 3 + Vite + Tailwind
- `trip-collab-api`: Spring Boot + PostgreSQL + Flyway

## Architecture Principles

- This service must not affect the existing `trip-collab-api`.
- This service does not write directly to the database.
- AI only returns drafts, explanations, or parsed results.
- Spring Boot remains responsible for token-based trip/member permissions, database writes, and business rules.
- FastAPI is responsible for LLM provider selection, prompts, schema validation, and fallback handling.
- Phase 0 uses `MockAIProvider`.
- Phase 0.5 adds structured logging for provider execution, timeout fallback, and provider error fallback.
- `OpenRouterProvider` is intentionally present but not implemented until Phase 1.

## Install

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` if local overrides are needed.

```bash
AI_PROVIDER=mock
APP_ENV=local
LOG_LEVEL=INFO
```

Supported Phase 0 provider:

- `mock`

Reserved for Phase 1:

- `openrouter`

## Run Server

```bash
uvicorn app.main:app --reload --port 8001
```

Health check:

```bash
curl http://127.0.0.1:8001/health
```

Expected response:

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "service": "trip-collab-ai",
    "env": "local",
    "provider": "mock"
  },
  "error": null
}
```

## Test

```bash
pytest
```

## Phase 0.5 Observability

All AI endpoint calls go through `AIService`.

`AIService` wraps provider calls with timeout and fallback handling. Provider exceptions are not returned as raw endpoint errors. Instead, the service returns a safe fallback result that still matches the existing response schema.

Structured logs include:

- `task_name`
- `provider_name`
- `request_id`
- `success`
- `fallback`
- `fallback_reason`
- `duration_ms`

Fallback reasons currently include:

- `none`
- `timeout`
- `provider_error`

The API response contract remains:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

## Mock Endpoint Examples

### Generate Itinerary Draft

```bash
curl -X POST http://127.0.0.1:8001/ai/itinerary/generate \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": "trip_123",
    "destination": "Tokyo",
    "days": 3,
    "preferences": ["food", "museum"]
  }'
```

### Explain Settlement

```bash
curl -X POST http://127.0.0.1:8001/ai/settlement/explain \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": "trip_123",
    "expenses_summary": {
      "currency": "TWD",
      "members": ["Ann", "Ben"],
      "total": 3000
    }
  }'
```

### Parse Receipt Draft

```bash
curl -X POST http://127.0.0.1:8001/ai/receipt/parse \
  -H "Content-Type: application/json" \
  -d '{
    "raw_text": "Mock receipt text"
  }'
```

## Git Collaboration

- Keep `.env` out of Git.
- Commit `.env.example` when configuration keys change.
- Keep provider implementations isolated under `app/providers`.
- Keep API contracts in `app/schemas`.
- Add focused tests for each new behavior before connecting real LLM providers.
- Do not introduce database access into this service.

## Phase 1 OpenRouter Plan

`OpenRouterProvider` will be implemented in Phase 1. It should handle:

- request timeout
- rate limit responses
- quota exceeded responses
- invalid JSON from the model
- fallback behavior
- retry limits from settings
