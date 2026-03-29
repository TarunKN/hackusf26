# API Layer

FastAPI application that serves as the backend for FormCoach. It mounts the Google ADK agent app, exposes a file upload endpoint for the form coach, and serves the frontend SPA.

---

## Entry Point — `main.py`

```bash
python api/main.py
# → http://localhost:8000/ui/
```

### What it does

1. **Mounts the ADK app** via `get_fast_api_app()` — this automatically exposes `/run`, `/stream`, and `/sessions` endpoints for the orchestrator agent.
2. **Serves the frontend** at `/ui/` as a static SPA (`frontend/index.html`).
3. **Exposes `/upload/form-image`** for server-side image uploads (used when the form coach agent needs a local file path).
4. **Exposes `/health`** for container health checks.

### Path resolution

Works both locally (running from `hackusf26/`) and in Docker (`WORKDIR /app`):

```python
_HERE = Path(__file__).resolve().parent   # .../api
_ROOT = _HERE.parent                       # .../hackusf26 or /app
_AGENTS = _ROOT / "fitness-agents"
```

---

## Endpoints

### `POST /run`
ADK agent run endpoint. Sends a message to the orchestrator and returns the full response.

**Request body:**
```json
{
  "app_name": "orchestration",
  "user_id": "u_abc123",
  "session_id": "sess_xyz",
  "new_message": {
    "role": "user",
    "parts": [{ "text": "What should I eat before training?" }]
  }
}
```

**Response:** Array of ADK event objects. The frontend walks them in reverse to find the last model turn.

### `POST /stream`
ADK streaming run. Same request format as `/run`, returns server-sent events.

### `GET/POST /sessions/*`
ADK session management endpoints (create, get, list, delete sessions).

### `POST /upload/form-image`
Accepts an image or video file, saves it to `UPLOAD_DIR`, and returns the server-side path.

**Accepted types:** `image/jpeg`, `image/png`, `image/webp`, `video/mp4`, `video/quicktime`

**Response:**
```json
{
  "image_path": "/tmp/formcoach_uploads/tmpXXXXXX.jpg",
  "filename": "squat.jpg",
  "size_bytes": 204800
}
```

> **Note:** The frontend primarily uses the Gemini File API directly (client-side) for video analysis. This endpoint is used when the form coach agent needs a local file path for server-side analysis via the ADK tool.

### `GET /health`
```json
{ "status": "ok", "service": "FormCoach Fitness Agent System" }
```

### `GET /ui/` and `GET /ui`
Serves `frontend/index.html`. All other `/ui/*` paths serve static assets from the `frontend/` directory.

---

## ADK Configuration

```python
api = get_fast_api_app(
    agents_dir="fitness-agents/agents",  # ADK discovers agents here
    session_service_uri=None,            # None = in-memory sessions (default)
    allow_origins=["*"],                 # CORS — tighten in production
    web=False,
    auto_create_session=True,            # Creates session if it doesn't exist
)
```

**Session storage:** In-memory by default. Set `SESSION_SERVICE_URI` to a database URI for persistent sessions across restarts.

---

## CORS

Currently set to `allow_origins=["*"]` for development. In production, restrict this to your actual frontend domain.

---

## Running in Development

```bash
# From hackusf26/
python api/main.py
```

Uvicorn runs with `reload=True` in dev mode — file changes restart the server automatically.

```bash
# Or with uvicorn directly (more control)
uvicorn api.main:api --host 0.0.0.0 --port 8000 --reload
```

---

## Running in Docker

See [`docker-compose.yml`](../docker-compose.yml) and [`Dockerfile`](../Dockerfile) in the project root.

```bash
docker compose up --build
```

The Docker setup:
1. Builds the API container from `Dockerfile`
2. Runs nginx as a reverse proxy (see `nginx.conf`)
3. nginx serves the frontend static files directly and proxies API calls to the FastAPI container

---

## Environment Variables

All config is loaded from `.env` via `shared/config.py`. See the [project README](../README.md#environment-variables) for the full list.
