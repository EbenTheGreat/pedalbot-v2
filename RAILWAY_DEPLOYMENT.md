# Railway Deployment Guide

Deploy PedalBot with **Railway** (backend + Celery worker + Redis) and **Streamlit Cloud** (frontend).

---

## Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select **EbenTheGreat/pedalbot-v2**
4. Railway will auto-detect the Dockerfile and deploy the **FastAPI API**

---

## Step 2: Add Redis

1. Inside your Railway project, click **+ New** → **Database** → **Redis**
2. Railway creates a Redis instance and provides `REDIS_URL`
3. This will be used by Celery as its message broker

---

## Step 3: Add Celery Worker Service

1. Inside the same project, click **+ New** → **GitHub Repo** → select **pedalbot-v2** again
2. Rename this service to **celery-worker**
3. Go to **Settings** for this service:
   - **Root directory**: `/` (leave default)
   - **Custom Dockerfile path**: `Dockerfile.celery`
   - **Custom start command**: `celery -A backend.workers.celery_app worker --loglevel=info --concurrency=2 -Q default,ingestion,pricing,notifications`

> [!IMPORTANT]
> Make sure the worker uses `Dockerfile.celery`, **not** the default `Dockerfile`. If the worker logs show "Uvicorn running...", the wrong Dockerfile is being used.

> [!NOTE]
> No shared volume is needed between the API and worker. Uploaded PDFs are stored in MongoDB GridFS, so both services can access them through the shared MongoDB connection.

---

## Step 4: Set Environment Variables

For **both** the API and Celery worker services, set these env vars:

| Variable | Value |
|----------|-------|
| `MONGODB_URI` | Your MongoDB Atlas connection string |
| `MONGODB_DB_NAME` | `pedalbot_db` |
| `PINECONE_API_KEY` | From [app.pinecone.io](https://app.pinecone.io) |
| `PINECONE_INDEX_NAME` | `pedalbot` |
| `GROQ_API_KEY` | From [console.groq.com](https://console.groq.com) |
| `VOYAGEAI_API_KEY` | From [dash.voyageai.com](https://dash.voyageai.com) |
| `GOOGLE_VISION_CREDENTIALS` | Base64-encoded JSON (see below) |
| `REVERB_API_KEY` | From [reverb.com/developer](https://reverb.com/developer) |
| `ENV` | `production` |

**For Redis connection** — use Railway's variable referencing:
| Variable | Value |
|----------|-------|
| `REDIS_URI` | `${{Redis.REDIS_URL}}` |
| `CELERY_BROKER_URL` | `${{Redis.REDIS_URL}}` |

### Encode Google Vision Credentials

```bash
base64 -i google-vision-credentials.json | tr -d '\n'
# Copy output → paste as GOOGLE_VISION_CREDENTIALS
```

---

## Step 5: Deploy Frontend on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app** → connect **EbenTheGreat/pedalbot-v2**
3. Set **Main file path**: `frontend/Home.py`
4. In **Settings → Secrets**, add:

```toml
PEDALBOT_API_URL = "https://your-railway-api-url.up.railway.app"
```

> Get the URL from your Railway API service → **Settings → Networking → Public Domain**

---

## Step 6: Verify

```bash
# Backend health check
curl https://your-railway-api-url.up.railway.app/health
```

Open the Streamlit URL, pick a pedal, and ask a question.

---

## Architecture on Railway

```
┌─────────────────────────────────────────┐
│           Railway Project               │
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │ FastAPI   │  │ Celery   │  │ Redis │ │
│  │ API       │→ │ Worker   │← │       │ │
│  │ (Docker)  │  │ (Docker) │  │       │ │
│  └──────────┘  └──────────┘  └───────┘ │
│       ↑                                 │
└───────┼─────────────────────────────────┘
        │
  ┌──────────┐        ┌──────────────┐
  │ Streamlit│        │ MongoDB Atlas│
  │ Cloud    │        │ (external)   │
  └──────────┘        └──────────────┘
```

---

## Pricing

Railway offers $5/month of free usage on the Hobby plan. Typical costs:
- **FastAPI API**: ~$3-5/month
- **Celery Worker**: ~$3-5/month
- **Redis**: ~$1-3/month
- **Total**: ~$7-13/month (much more capable than Render free tier)
