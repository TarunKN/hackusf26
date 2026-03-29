# Frontend

Single-page application for FormCoach. Built with vanilla JavaScript and no build step — just one `index.html` file served directly by the FastAPI backend.

Open at **`http://localhost:8000/ui/`** after starting the server.

---

## Architecture

```
index.html
    │
    ├── State (S object)          — all app state in memory + localStorage
    ├── Navigation (showView)     — tab switching, sidebar highlighting
    ├── Onboarding                — multi-step profile wizard
    ├── Dashboard                 — stats, check-in, flags
    ├── Form Coach                — upload, Gemini analysis, results
    ├── Nutrition                 — macros, food log, meal suggestions
    ├── Workout Planner           — plan generation, session logging
    ├── Ask Coach (chat)          — orchestrator chat + TTS
    └── Settings                 — API URL, Gemini key, profile
```

No frameworks, no bundler, no `node_modules`. The entire app is ~4,200 lines of HTML/CSS/JS.

---

## State Management

All state lives in the `S` object:

```javascript
const S = {
  apiUrl: "http://localhost:8000",  // Backend URL
  geminiKey: "",                    // Gemini API key (client-side vision)
  profile: {},                      // User profile from onboarding
  goals: [],                        // Selected fitness goals
  sessionId: "sess_...",            // ADK session ID
  macros: null,                     // Calculated macro targets
  foodLog: [],                      // Today's food entries
  formAnalyses: [],                 // Form analysis history
  sessions: 0,                      // Completed training sessions
  mood: null,                       // Today's mood score
  energy: null,                     // Today's energy score
  flags: {},                        // Active alert flags
  currentView: "dashboard",         // Active tab
};
```

`S.apiUrl`, `S.geminiKey`, and `S.profile` are persisted to `localStorage` under `fc_state`. TTS preferences (API key, voice) are persisted under `fc_tts`.

---

## Views

### Dashboard (`view-dashboard`)
- Stat tiles: form score, calories today, sessions logged, mood/energy
- Daily check-in card (mood + energy → sent to orchestrator)
- Active flags panel (medical alerts, low energy warnings)

### Form Coach (`view-formcoach`)
- **Media upload** — drag-and-drop or click to upload photo/video
  - Images: base64 inline → Gemini Vision API (direct, no server)
  - Videos: Gemini File API upload → poll until ACTIVE → multi-frame analysis
- **Analysis config** — exercise selector, focus area chips
- **Results** — verdict badge, issues list with severity bars, coaching cues
- After analysis: automatically redirects to **Ask Coach** tab

### Nutrition (`view-nutrition`)
- **Macro targets tab** — calculates TDEE + macros via Mifflin-St Jeor
- **Food log tab** — log entries with running daily totals vs. targets
- **Meal suggestions tab** — agent generates 3 tailored meal ideas

### Workout Planner (`view-workout`)
- **Generate plan** — PPL / Upper-Lower / Full Body, 3–6 days/week
- **Log session** — RPE tracking with automatic progression recommendation
- After logging: redirects to **Ask Coach** tab with progression message

### Ask Coach (`view-chat`)
- Chat interface connected to the ADK orchestrator via `POST /run`
- Form analysis results are injected as rich cards automatically
- **ElevenLabs TTS** — coach speaks responses aloud
  - Toggle "Coach speaks responses" checkbox to enable
  - Enter ElevenLabs API key + select voice
  - **⏸ Pause** button always visible when TTS is on
  - Changes to **■ Stop** while audio is playing
  - Click to interrupt the coach mid-sentence

### Settings (`view-settings`)
- API base URL (for pointing at ngrok or production)
- Gemini API key
- Profile summary
- Reset & re-onboard

---

## Key Functions

### Navigation
```javascript
showView(name, callerEl)
// Switches active view, updates sidebar highlight
// name: "dashboard" | "formcoach" | "nutrition" | "workout" | "chat" | "settings"
```

### Form Analysis
```javascript
runFormAnalysis()
// Orchestrates the full analysis flow:
// 1. Validates inputs (file, exercise, Gemini key)
// 2. For videos: uploadVideoToGeminiFileAPI() → callGeminiVisionFileUri()
// 3. For images: fileToB64() → callGeminiVision()
// 4. renderFormResults() → injectFormCoachToChat() → showView("chat")

uploadVideoToGeminiFileAPI(file, mime)
// Uploads video to Gemini File API (resumable upload)
// Polls until state === "ACTIVE"
// Returns file URI for use in generateContent

callGeminiVisionFileUri(fileUri, mime, prompt)
// Calls Gemini generateContent with file_data (full video analysis)

callGeminiVision(b64, mime, prompt)
// Calls Gemini generateContent with inline_data (image analysis)

injectFormCoachToChat(result, exercise)
// Injects rich form card into chat history
// Sends summary to orchestrator
// Redirects to Ask Coach tab
```

### Chat / Orchestrator
```javascript
agentRun(message)
// POST /run → ADK orchestrator
// Walks response events in reverse to find last model turn
// Returns text string

addChatMsg(role, text)
// Appends message to chat history
// Speaks via ElevenLabs TTS if enabled (role === "agent")

sendChat()
// Reads input, calls agentRun(), displays response
```

### TTS (ElevenLabs)
```javascript
toggleTTS(on)
// Enables/disables TTS, shows/hides Pause button and key field

speakWithElevenLabs(text)
// Strips markdown, calls ElevenLabs /v1/text-to-speech/{voiceId}
// Plays audio blob, updates button state

stopTTS()
// Pauses and clears current audio
// Resets button to "⏸ Pause" (stays visible if TTS is on)

loadMyVoices()
// Fetches user's ElevenLabs voices and populates dropdown
```

---

## Gemini Integration

The frontend calls Gemini directly from the browser using the user's own API key (entered during onboarding, stored in `localStorage`). No media bytes touch the backend.

**Model:** `gemini-2.5-flash` with `responseMimeType: "application/json"` and an enforced `responseSchema` for consistent structured output.

**Video flow (Gemini File API):**
1. `POST https://generativelanguage.googleapis.com/upload/v1beta/files` — initiate resumable upload
2. `POST {resumableUri}` with file bytes — upload and finalize
3. `GET https://generativelanguage.googleapis.com/v1beta/{file.name}` — poll until `state === "ACTIVE"`
4. `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent` — analyze with `file_data`

---

## ElevenLabs TTS Integration

Optional voice feature. Uses the standard `/v1/text-to-speech/{voice_id}` endpoint.

**Free-tier voices included** (no custom voice needed):
- Jessica, Chris, Daniel, Charlotte, Lily, Brian, Callum, Charlie, Matilda, Will

**Model:** `eleven_turbo_v2_5` (lowest latency)

**Voice settings:** stability 0.45, similarity_boost 0.80, style 0.15, speaker_boost on

---

## Styling

CSS custom properties (variables) for the full design system:

```css
--bg, --bg1, --bg2, --bg3     /* Dark background layers */
--lime, --lime2, --lime-dim   /* Primary accent (yellow-green) */
--orange, --orange-dim        /* Warning / secondary accent */
--red, --red-dim              /* Danger */
--green, --green-dim          /* Success */
--blue, --blue-dim            /* Info */
--text, --text2, --text3      /* Text hierarchy */
```

Fonts: **Bebas Neue** (display/headings), **DM Sans** (body), **DM Mono** (labels/code)

---

## Local Development

No build step needed. Just open the file directly or serve it via the FastAPI backend:

```bash
# Via backend (recommended — enables /run API calls)
python api/main.py
# Open http://localhost:8000/ui/

# Direct file open (form analysis works, /run calls will fail)
open frontend/index.html
```
