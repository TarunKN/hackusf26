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
    ├── Gemini Vision API ──────────────────── Form analysis (direct, client-side)
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

---

## Project Structure

```
hackusf26/
├── api/
│   └── main.py              # FastAPI entrypoint — mounts ADK + serves frontend
├── fitness-agents/
│   └── agents/
│       ├── orchestration/   # Root orchestrator (ADK entry point)
│       ├── form_coach/      # Form analysis via Gemini Vision
│       ├── nutrition/       # Macro calculation + meal suggestions
│       └── workout_planner/ # Periodized training plans
├── frontend/
│   └── index.html           # Single-page app (vanilla JS, no build step)
├── shared/
│   ├── config.py            # Environment config
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

| Agent | Responsibility |
|---|---|
| **Orchestrator** | Root agent. Routes messages, proactively connects signals (e.g. bad form → adjust workout plan) |
| **Form Coach** | Analyzes exercise form from images/video using Gemini 2.5 Flash Vision. Returns score, issues, coaching cues |
| **Nutrition** | Calculates TDEE + macro targets (Mifflin-St Jeor). Logs food, generates meal suggestions |
| **Workout Planner** | Builds PPL/Upper-Lower/Full Body plans. Tracks RPE, adjusts load based on recovery signals |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model for agent reasoning |
| `GEMINI_VISION_MODEL` | `gemini-2.5-flash` | Model for form analysis |
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI bind port |
| `UPLOAD_DIR` | `/tmp/formcoach_uploads` | Image upload directory |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Features

- **Form analysis** — Upload a photo or video of any exercise. Gemini Vision returns a verdict (excellent/good/decent/bad/dangerous), biomechanical issues with severity, and actionable coaching cues
- **Form → Chat integration** — After every analysis, results are automatically injected into the Ask Coach chat with an orchestrator follow-up
- **Macro calculator** — Personalized TDEE using Mifflin-St Jeor, adjusted per goal (fat loss, hypertrophy, strength, endurance)
- **Meal suggestions** — Agent generates 3 tailored meal ideas respecting dietary restrictions and calorie budget
- **Workout plans** — PPL, Upper/Lower, Full Body splits with RPE tracking and progressive overload
- **Daily check-in** — Mood/energy logging that automatically adjusts training volume
- **ElevenLabs TTS** — Coach speaks responses aloud (toggle in Ask Coach tab, free voices included)
- **Onboarding** — Multi-step profile setup that personalizes all agents
