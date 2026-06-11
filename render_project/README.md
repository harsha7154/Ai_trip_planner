# Odisha AI Trip Planner

AI-powered FastAPI backend + HTML frontend for planning Odisha trips.

---

## Project Structure

```
odisha-trip-planner/
├── app/                    # FastAPI backend
│   ├── main.py             # Entry point, serves /ui frontend too
│   ├── api/routes.py       # All HTTP endpoints
│   ├── core/config.py      # Settings via env vars
│   ├── data/loader.py      # Excel data loader
│   ├── services/           # trip, weather, place_filter
│   ├── ai/llm.py           # Groq + Gemini LLM calls
│   ├── geo/                # Distance + constants
│   ├── schemas/            # Pydantic models
│   └── monitoring/         # Prometheus + logging
├── data/
│   └── places.xlsx         # Odisha places dataset
├── frontend/
│   └── index.html          # Single-file UI
├── tests/
├── requirements.txt
├── render.yaml             # Render deploy config
├── .env.example            # Copy to .env for local dev
└── .gitignore
```

---

## Local Development

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/odisha-trip-planner.git
cd odisha-trip-planner

# 2. Create venv (local only — never commit)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env and fill in your API keys

# 5. Run
uvicorn app.main:app --reload --port 8000

# 6. Open
# API docs:  http://127.0.0.1:8000/docs
# Frontend:  http://127.0.0.1:8000/ui
```

---

## Deploy to Render

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/odisha-trip-planner.git
git push -u origin main
```

### Step 2 — Create Render Web Service
1. Go to https://render.com → **New → Web Service**
2. Connect your GitHub account and select this repo
3. Render auto-detects `render.yaml` — confirm settings:
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Click **Create Web Service**

### Step 3 — Add Secret Environment Variables
In Render Dashboard → your service → **Environment** tab, add:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | your Groq key |
| `GEMINI_API_KEY` | your Gemini key |
| `OPENWEATHER_API_KEY` | your OpenWeather key |
| `GEOAPIFY_API_KEY` | your Geoapify key |

Click **Save Changes** — Render redeploys automatically.

### Step 4 — Get Your Render URL
After deploy completes, Render shows your URL at the top:
```
https://odisha-trip-planner.onrender.com
```
(exact name depends on what you typed in Step 2)

---

## Connecting the Frontend to the Backend

The frontend is **served from the same backend** at `/ui`.

### Option A — Use the built-in UI (easiest)
Visit: `https://your-app.onrender.com/ui`

The frontend auto-detects the backend URL from `window.location.origin`, so **no configuration needed**.

### Option B — Host frontend separately (GitHub Pages / Netlify)
1. Open `frontend/index.html` in a text editor
2. In the **Backend URL** field on the page, paste your Render URL:
   ```
   https://your-app.onrender.com
   ```
3. Click **Test** to verify connection
4. Update `CORS_ORIGINS` in Render → Environment:
   ```
   CORS_ORIGINS=["https://yourname.github.io"]
   ```

---

## Verify the Deployment

After deploy, run these checks in order:

### 1. Health check
```
GET https://your-app.onrender.com/health
```
Expected: `{"status":"healthy","places_loaded":123,...}`

### 2. API docs
```
https://your-app.onrender.com/docs
```
All endpoints should be listed and testable.

### 3. Frontend UI
```
https://your-app.onrender.com/ui
```
The trip planner UI loads. Click **Test** (connection status should turn green ✅).

### 4. End-to-end test
Fill in the form and click **Generate Itinerary** — you should receive a full day-wise plan.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |
| GET | `/ui` | Frontend HTML |
| POST | `/api/v1/plan` | Generate trip itinerary |
| GET | `/api/v1/places` | List places |
| POST | `/api/v1/places/filter` | Filter places |
| GET | `/api/v1/districts` | List districts |
| GET | `/api/v1/categories` | List categories |
| GET | `/api/v1/weather/{city}` | Weather forecast |

---

## Notes

- **Free Render tier** spins down after 15 min of inactivity. First request after sleep takes ~30s.
- **venv folder** is in `.gitignore` — never commit it. Render installs deps fresh from `requirements.txt`.
- **`.env` file** is in `.gitignore` — set secrets via Render Dashboard, not code.
