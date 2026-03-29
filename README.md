# FormCoach — AI Fitness System

An AI-powered personal fitness system built with **Google ADK** (Agent Development Kit) and **Gemini 2.5 Flash**. Four specialist agents — Form Coach, Nutritionist, Workout Planner, and Orchestrator — work together to keep you progressing safely.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser (frontend/index.html)                          │
│  • Onboarding  • Form Coach  • Nutrition  • Chat        │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP / REST
┌────────────────────▼────────────────────────────────────┐
│  Nginx (port 80/443)                                    │
│  • Serves static frontend                               │
│  • Proxies /run /stream /sessions /upload → API         │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  FastAPI + Google ADK  (api/main.py, port 8000)         │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Orchestrator Agent (root)                      │   │
│  │  ├── Form Coach Agent  (Gemini Vision)          │   │
│  │  ├── Nutrition Agent   (macro calc + meals)     │   │
│  │  └── Workout Planner   (periodized plans)       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Start (Local)

### 1. Prerequisites

- Python 3.11+
- A [Gemini API key](https://aistudio.google.com/app/apikey)

### 2. Install dependencies

```bash
cd hackusf26
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY
```

`.env` contents:
```
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash
GEMINI_VISION_MODEL=gemini-2.5-flash
```

### 4. Run the API server

```bash
python api/main.py
# Server starts at http://localhost:8000
```

### 5. Open the frontend

Open `frontend/index.html` in your browser (or serve it with any static server):

```bash
# Python simple server
python -m http.server 3000 --directory frontend
# Then open http://localhost:3000
```

In the onboarding screen, set **API Base URL** to `http://localhost:8000` and enter your **Gemini API Key**.

---

## Docker (Local Container)

### Build and run with Docker Compose

```bash
# Copy and fill in your API key
cp .env.example .env
echo "GEMINI_API_KEY=AIza..." >> .env

# Build and start
docker compose up --build

# Open http://localhost in your browser
```

The compose stack runs:
- **`api`** — FastAPI + ADK backend on port 8000 (internal)
- **`nginx`** — Serves frontend + proxies API on port 80

### Build the API image only

```bash
docker build -t formcoach-api .
docker run -p 8000:8000 -e GEMINI_API_KEY=AIza... formcoach-api
```

---

## Deploy to Fly.io

### First-time setup

```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
brew install flyctl   # macOS
# or: curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create the app (only once)
fly launch --no-deploy --name formcoach-ai --region mia

# Set your Gemini API key as a secret
fly secrets set GEMINI_API_KEY=AIza...

# Create a persistent volume for uploads
fly volumes create formcoach_uploads --region mia --size 1

# Deploy
fly deploy
```

### Subsequent deploys

```bash
fly deploy
```

### View logs

```bash
fly logs
```

### Open the live app

```bash
fly open
```

---

## Deploy to Railway

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select this repository
4. Add environment variable: `GEMINI_API_KEY=AIza...`
5. Railway auto-detects the `Dockerfile` and deploys

The frontend is served by nginx inside the container. Set the **API Base URL** in the app's onboarding to your Railway public URL.

---

## Deploy to Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your repo, select **Docker** runtime
4. Set environment variable: `GEMINI_API_KEY=AIza...`
5. Deploy

---

## Project Structure

```
hackusf26/
├── api/
│   ├── main.py          # FastAPI entrypoint, mounts ADK app
│   └── routes.py        # Additional REST routes
├── fitness-agents/
│   └── agents/
│       ├── orchestration/
│       │   └── agent.py # Root orchestrator (entry point for ADK)
│       ├── form_coach/
│       │   ├── agent.py # Form Coach ADK agent
│       │   └── vision.py# Gemini Vision API integration
│       ├── nutrition/
│       │   ├── agent.py # Nutrition ADK agent
│       │   ├── macros.py# Deterministic macro calculations
│       │   └── meal-planner.py
│       └── workout_planner/
│           └── agent.py # Workout Planner ADK agent
├── frontend/
│   └── index.html       # Single-page app (vanilla JS)
├── shared/
│   ├── config.py        # Environment config
│   ├── schemas.py       # Pydantic schemas
│   └── utils.py         # Shared utilities
├── Dockerfile           # API container
├── docker-compose.yml   # Full stack (API + nginx)
├── nginx.conf           # Nginx: static frontend + API proxy
├── fly.toml             # Fly.io deployment config
└── requirements.txt
```

---

## Agents

### Orchestrator
The root agent. Every user message goes here first. It:
- Routes to specialist sub-agents based on intent
- Proactively connects signals (e.g. bad form → adjust workout plan)
- Manages user profile and daily check-ins

### Form Coach
- Accepts image/video uploads via `/upload/form-image`
- Calls **Gemini 2.5 Flash Vision** with a biomechanically-informed prompt
- Returns a 0-100 form score, issues with severity, and coaching cues
- Flags major issues to the orchestrator for workout plan adjustment
- Results are automatically injected into the Orchestrator chat

### Nutrition Agent
- Calculates TDEE and macro targets (Mifflin-St Jeor equation)
- Logs food entries and tracks daily totals vs. targets
- Generates meal suggestions tailored to dietary restrictions and goals
- Cross-references nutrition with scheduled training sessions

### Workout Planner
- Generates periodized weekly plans (PPL, Upper/Lower, Full Body)
- Tracks session-by-session progression with RPE
- Adjusts training load based on recovery signals (mood, energy, form flags)

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model for agent reasoning |
| `GEMINI_VISION_MODEL` | `gemini-2.5-flash` | Model for form analysis vision |
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI bind port |
| `UPLOAD_DIR` | `/tmp/formcoach_uploads` | Directory for uploaded images |
| `LOG_LEVEL` | `INFO` | Logging level |
| `USE_CLOUD_LOGGING` | `false` | Enable Google Cloud Logging |

---

## Development Notes

- The frontend calls the ADK `/run` endpoint directly. The ADK returns an **array of event objects**; the frontend parses the last `model` role event for the response text.
- Form analysis runs **client-side** (Gemini Vision called directly from the browser with the user's API key) for low latency. The backend `analyze_exercise_form` tool is available for server-side analysis when the API key is configured server-side.
- The `RETRY_OPTIONS` dict in `shared/config.py` is passed to `Gemini()` agents for automatic retry on rate limits.
