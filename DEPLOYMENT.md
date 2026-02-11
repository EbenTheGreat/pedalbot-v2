# PedalBot Deployment Guide

Deploy PedalBot with **Render** (backend) + **Streamlit Cloud** (frontend).

---

## Step 1: Set Up MongoDB Atlas

1. Go to [cloud.mongodb.com](https://cloud.mongodb.com)
2. Create a free cluster (M0)
3. Create database user with password
4. Get connection string: `mongodb+srv://user:pass@cluster.mongodb.net/pedalbot_db`
5. **Network Access**: Add `0.0.0.0/0` to allow connections from Render

---

## Step 2: Push to GitHub

```bash
cd /Users/solomonolakulehin/Desktop/eben/pedalbot-langgraph-main

# Initialize git (if not already)
git init

# Add all files (secrets excluded via .gitignore)
git add .
git commit -m "Initial commit for deployment"

# Create GitHub repo and push
# Option A: GitHub CLI
gh repo create pedalbot --public --source=. --push

# Option B: Manual
# 1. Create repo on github.com
# 2. git remote add origin https://github.com/YOUR_USERNAME/pedalbot.git
# 3. git push -u origin main
```

---

## Step 3: Deploy Backend on Render

1. Go to [render.com](https://render.com) → New → **Blueprint**
2. Connect your GitHub repo
3. Render auto-detects `render.yaml`
4. Set environment variables manually:

| Variable | Value |
|----------|-------|
| `MONGODB_URI` | Your Atlas connection string |
| `PINECONE_API_KEY` | From pinecone.io |
| `GROQ_API_KEY` | From console.groq.com |
| `VOYAGEAI_API_KEY` | From voyageai.com |
| `GOOGLE_VISION_CREDENTIALS` | Base64-encoded JSON (see below) |
| `REVERB_API_KEY` | From reverb.com/developer |

### Encode Google Vision Credentials

```bash
# Mac/Linux
base64 -i google-vision-credentials.json | tr -d '\n'

# Copy output → paste as GOOGLE_VISION_CREDENTIALS in Render
```

5. Click **Deploy** → Wait for green status
6. Note your URL: `https://pedalbot-api.onrender.com`

---

## Step 4: Deploy Frontend on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app**
3. Connect your GitHub repo
4. Set:
   - **Main file path**: `frontend/Home.py`
   - **App URL**: your-app-name
5. Go to **Settings → Secrets** and add:

```toml
PEDALBOT_API_URL = "https://pedalbot-api.onrender.com"
```

6. Deploy!

---

## Step 5: Verify

1. Open your Streamlit app
2. Select a pedal
3. Ask a question
4. Confirm it works! 🎉

---

## Troubleshooting

### Backend not responding
- Check Render logs
- Verify environment variables
- Ensure MongoDB Atlas allows `0.0.0.0/0`

### Frontend can't connect
- Check `PEDALBOT_API_URL` secret
- Ensure backend is healthy: `https://your-app.onrender.com/health`

### Celery worker errors
- Check Redis connection
- Verify `CELERY_BROKER_URL` is set

---

## Environment Variables Summary

### Backend (Render)
```
MONGODB_URI=mongodb+srv://...
PINECONE_API_KEY=...
GROQ_API_KEY=...
VOYAGEAI_API_KEY=...
JWT_SECRET_KEY=(auto-generated)
GOOGLE_VISION_CREDENTIALS=(base64)
REVERB_API_KEY=...
ENV=production
```

### Frontend (Streamlit Cloud)
```toml
PEDALBOT_API_URL = "https://pedalbot-api.onrender.com"
```
