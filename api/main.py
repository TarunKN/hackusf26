"""
api/main.py
FastAPI entrypoint. Mounts the ADK app and adds REST routes for
image upload (used by the form coach agent).
Also serves the frontend static files at the root path.
"""

import os
import sys
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from google.adk.cli.fast_api import get_fast_api_app

# ── Path setup ────────────────────────────────────────────────────────────────
# Works both locally (running from hackusf26/) and in Docker (WORKDIR /app)
_HERE = Path(__file__).resolve().parent          # /app/api  or  .../hackusf26/api
_ROOT = _HERE.parent                              # /app      or  .../hackusf26
_AGENTS = _ROOT / "fitness-agents"

for _p in [str(_ROOT), str(_AGENTS)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.config import API_HOST, API_PORT, USE_CLOUD_LOGGING, LOG_LEVEL

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

if USE_CLOUD_LOGGING:
    import google.cloud.logging
    google.cloud.logging.Client().setup_logging()

# ── FastAPI app ───────────────────────────────────────────────────────────────

# get_fast_api_app wraps the ADK App and mounts /run, /stream, /sessions endpoints
api = get_fast_api_app(
    agents_dir=str(Path(__file__).parent.parent / "fitness-agents" / "agents"),
    session_service_uri=os.getenv("SESSION_SERVICE_URI", None),  # None = in-memory
    allow_origins=["*"],  # Tighten this in production
    web=False,
    auto_create_session=True,
)

# ── Frontend static files ──────────────────────────────────────────────────────
# Serve the frontend SPA. Mount AFTER ADK routes so /run, /stream, /health etc.
# take priority. The frontend is served at /ui/ to avoid ADK's POST-only / route.

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    @api.get("/ui", include_in_schema=False)
    @api.get("/ui/", include_in_schema=False)
    async def serve_index():
        """Serve the main frontend SPA."""
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    # Mount static assets under /ui
    api.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    logger.info(f"[frontend] Serving frontend from {FRONTEND_DIR} at /ui/")
    logger.info(f"[frontend] Open: http://localhost:{API_PORT}/ui/")
else:
    logger.warning(f"[frontend] Frontend directory not found at {FRONTEND_DIR}")

# ── Image upload endpoint ──────────────────────────────────────────────────────
# The form coach agent receives image_path as a string tool argument.
# This endpoint accepts the file from the frontend, saves it temporarily,
# and returns the path so the agent tool can read it.

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/formcoach_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@api.post("/upload/form-image")
async def upload_form_image(file: UploadFile = File(...)):
    """
    Accept an image or video file from the frontend.
    Returns the server-side path to pass as `image_path` in the
    analyze_exercise_form tool call.
    """
    allowed_types = {"image/jpeg", "image/png", "image/webp", "video/mp4", "video/quicktime"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=415, detail=f"Unsupported media type: {file.content_type}")

    suffix = Path(file.filename).suffix or ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, dir=UPLOAD_DIR, suffix=suffix, mode='wb')
    try:
        contents = await file.read()
        tmp.write(contents)
        tmp.flush()
    finally:
        tmp.close()

    logger.info(f"[upload] Saved {file.filename} → {tmp.name} ({len(contents)/1024:.1f} KB)")
    return {"image_path": tmp.name, "filename": file.filename, "size_bytes": len(contents)}


# ── Health check ──────────────────────────────────────────────────────────────

@api.get("/health")
def health():
    return {"status": "ok", "service": "FormCoach Fitness Agent System"}


# ── Dev server ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:api", host=API_HOST, port=API_PORT, reload=True)