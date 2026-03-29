# FormCoach — AI Fitness System

> **HackUSF 2026** · Built with Google ADK + Gemini 2.5 Flash

An AI-powered personal fitness system with four specialist agents that work together: a **Form Coach** that analyzes your exercise technique via computer vision, a **Nutritionist** that calculates macros and suggests meals, a **Workout Planner** that builds periodized training programs, and an **Orchestrator** that coordinates everything and proactively connects signals across all agents.

---

## Demo

```
Frontend:  http://localhost:8000/ui/
API:       http://localhost:8000/health
```

---

## Architecture

```
Browser (frontend/index.html)
    │
    ├── Gemini File API ────────────────────── Video upload + multi-frame analysis
    ├── Gemini Vision API ──────────────────── Image form analysis (inline, client-side)
    ├── ElevenLabs TTS API ─────────────────── Coach voice (optional)
    │
    └── HTTP → FastAPI (api/main.py :8000)
                │
                └── Google ADK
                        │
                        ├── Orchestrator Agent  ← root, routes all messages
                        │       ├── Form Coach Agent   (Gemini Vision)
                        │       ├── Nutrition Agent    (macro calc + meals)
                        │       └── Workout Planner    (periodized plans)
                        │
                        └── /run /stream /sessions  ← ADK endpoints
```

### Key Design Decisions

- **Client-side vision** — Form analysis calls Gemini directly from the browser using the user's own API key. No media bytes touch the backend server, keeping it stateless and cheap to host.
- **Gemini File API for video** — Videos are uploaded to Google's File API for server-side processing, enabling true multi-frame analysis across the full clip (not just the first frame).
- **ADK orchestration** — The backend uses Google's Agent Development Kit (ADK) to manage multi-agent routing, session state, and sub-agent delegation. The orchestrator proactively connects signals between agents without the user asking.
- **Single-file frontend** — The entire UI is one `index.html` with no build step, making it trivial to deploy anywhere.

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- A [Gemini API key](https://aistudio.google.com/app/apikey)

### 2. Install

```bash
cd hackusf26
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY=AIza...
```

### 4. Run

```bash
python api/main.py
```

Open **`http://localhost:8000/ui/`** in your browser.

On first load, the onboarding wizard collects your profile (name, age, weight, height, goals, injuries, dietary restrictions). This personalizes every agent's responses.

---

## Expose Publicly (ngrok)

```bash
# Install ngrok: https://ngrok.com/download
# Get authtoken: https://dashboard.ngrok.com/get-started/your-authtoken

~/bin/ngrok config add-authtoken YOUR_TOKEN
~/bin/ngrok http 8000
# → https://abc123.ngrok-free.app/ui/
```

Or use the helper script:
```bash
bash start-ngrok.sh
```

---

## Docker

```bash
cp .env.example .env   # add GEMINI_API_KEY
docker compose up --build
# Open http://localhost/ui/
```

The Docker setup runs the FastAPI server behind nginx. Nginx serves the frontend static files and proxies `/run`, `/stream`, `/health`, and `/upload` to the API container.

---

## Project Structure

```
hackusf26/
├── api/
│   ├── main.py              # FastAPI entrypoint — mounts ADK + serves frontend
│   └── routes.py            # (reserved for additional REST routes)
├── fitness-agents/
│   └── agents/
│       ├── orchestration/   # Root orchestrator (ADK entry point)
│       │   ├── agent.py     # Orchestrator agent + tools
│       │   ├── memory.py    # Session state helpers
│       │   └── router.py    # Intent routing logic
│       ├── form_coach/      # Form analysis via Gemini Vision
│       │   ├── agent.py     # Form Coach agent + tools
│       │   ├── vision.py    # Gemini Vision API pipeline
│       │   └── utils/
│       │       └── pose-utils.py  # Deterministic biomechanical calculations
│       ├── nutrition/       # Macro calculation + meal suggestions
│       │   ├── agent.py     # Nutrition agent + tools
│       │   ├── macros.py    # Mifflin-St Jeor TDEE engine
│       │   └── meal-planner.py  # Meal plan template scaffolding
│       └── workout_planner/ # Periodized training plans
│           ├── agent.py     # Workout Planner agent + tools
│           ├── progression.py   # Progressive overload calculations
│           └── routines.py      # Pre-built split templates
├── frontend/
│   └── index.html           # Single-page app (vanilla JS, no build step)
├── shared/
│   ├── config.py            # Environment config (loaded from .env)
│   ├── schemas.py           # Pydantic schemas shared across agents
│   └── utils.py             # Logging callbacks, retry options
├── Dockerfile               # API container
├── docker-compose.yml       # Full stack (API + nginx)
├── nginx.conf               # Nginx: static frontend + API proxy
├── start-ngrok.sh           # One-command public URL via ngrok
└── requirements.txt
```

---

## Agents

| Agent | File | Responsibility |
|---|---|---|
| **Orchestrator** | `orchestration/agent.py` | Root agent. Routes messages, proactively connects signals (e.g. bad form → adjust workout plan). Entry point for all ADK requests. |
| **Form Coach** | `form_coach/agent.py` | Analyzes exercise form from images/video using Gemini 2.5 Flash Vision. Returns verdict, issues, and coaching cues. |
| **Nutrition** | `nutrition/agent.py` | Calculates TDEE + macro targets (Mifflin-St Jeor). Logs food, generates meal suggestions respecting dietary restrictions. |
| **Workout Planner** | `workout_planner/agent.py` | Builds PPL/Upper-Lower/Full Body plans. Tracks RPE, adjusts load based on recovery signals from other agents. |

### Cross-Agent Coordination

The orchestrator autonomously connects signals between agents without the user asking:

| Trigger | Automatic Action |
|---|---|
| Form Coach flags major issue | Orchestrator tells user + routes to Workout Planner to regress the exercise |
| Mood/energy ≤ 4 | Workout Planner reduces volume 40%, Nutrition adjusts to comfort foods |
| `medical_review_requested = True` | User is warned, movement is flagged, plan is adjusted |

---

## Features

### Form Coach
- Upload a **photo or video** of any exercise
- Videos are uploaded to the **Gemini File API** for full multi-frame analysis (not just the first frame)
- Returns a **verdict** (excellent / good / decent / bad / dangerous), biomechanical issues with severity (minor / moderate / major), and actionable coaching cues
- After every analysis, results are automatically injected into the **Ask Coach** chat with an orchestrator follow-up
- Redirects to the Ask Coach tab automatically after analysis completes

### Nutrition
- Personalized **TDEE** using Mifflin-St Jeor, adjusted per goal (fat loss −400 kcal, hypertrophy +300 kcal, etc.)
- **Food log** with running daily totals vs. targets
- Agent generates **3 tailored meal ideas** respecting dietary restrictions and calorie budget

### Workout Planner
- **PPL, Upper/Lower, Full Body** splits with configurable days per week
- **RPE tracking** with automatic progression recommendations (add load / hold / deload)
- Plan adjusts automatically when form issues or low energy are detected

### Ask Coach
- Chat with the orchestrator agent about anything fitness-related
- **ElevenLabs TTS** — coach speaks responses aloud (toggle in Ask Coach tab, free voices included)
- **⏸ Pause / ■ Stop** button to interrupt the coach mid-sentence
- Form analysis results are automatically injected as rich cards in the chat

### Dashboard
- Live snapshot: form score, calories today, sessions logged, mood/energy
- **Daily check-in** — mood and energy logging that automatically adjusts training volume
- Active flags panel showing any medical or recovery alerts

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key — used by backend agents |
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` | Model for agent reasoning (orchestrator, sub-agents) |
| `GEMINI_VISION_MODEL` | `gemini-2.5-flash` | Model for form analysis vision calls |
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI bind port |
| `UPLOAD_DIR` | `/tmp/formcoach_uploads` | Temp directory for uploaded images (server-side agent path) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `USE_CLOUD_LOGGING` | `false` | Enable Google Cloud Logging |
| `SESSION_SERVICE_URI` | *(none)* | ADK session backend URI (default: in-memory) |
| `RETRY_INITIAL_DELAY` | `2` | ADK retry initial delay (seconds) |
| `RETRY_MAX_DELAY` | `8` | ADK retry max delay (seconds) |
| `RETRY_ATTEMPTS` | `3` | ADK retry attempts before failing |

> **Note:** The frontend also uses a Gemini API key entered during onboarding (stored in `localStorage`). This key is used directly from the browser for form analysis — it is never sent to the backend.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/run` | ADK agent run (main chat endpoint) |
| `POST` | `/stream` | ADK streaming run |
| `GET/POST` | `/sessions/*` | ADK session management |
| `POST` | `/upload/form-image` | Upload image/video for server-side form analysis |
| `GET` | `/health` | Health check |
| `GET` | `/ui/` | Frontend SPA |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | [Google ADK](https://google.github.io/adk-docs/) |
| LLM | Gemini 2.5 Flash (vision + reasoning) |
| Backend | FastAPI + Uvicorn |
| Frontend | Vanilla JS, single HTML file |
| TTS | ElevenLabs API (optional) |
| Container | Docker + nginx |
| Tunnel | ngrok |
