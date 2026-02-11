# Streamlit Commands Guide

## Quick Start

### Run Streamlit (Development)
```bash
uv run streamlit run frontend/Home.py
```

This starts the Streamlit app on the default port **8501**.

---

## Common Commands

### Run on Custom Port
```bash
uv run streamlit run frontend/Home.py --server.port 8502
```

### Run on All Network Interfaces (for remote access)
```bash
uv run streamlit run frontend/Home.py --server.address 0.0.0.0
```

### Run Without Opening Browser
```bash
uv run streamlit run frontend/Home.py --server.headless true
```

### Disable File Watcher (Production)
```bash
uv run streamlit run frontend/Home.py --server.fileWatcherType none
```

---

## Full Development Setup

Run both **FastAPI** and **Streamlit** together:

### Terminal 1 - FastAPI Backend
```bash
uv run uvicorn backend.main:app --reload --port 8000
```

### Terminal 2 - Streamlit Frontend
```bash
uv run streamlit run frontend/Home.py
```

---

## URLs After Starting

| Service | URL |
|---------|-----|
| Streamlit Frontend | http://localhost:8501 |
| FastAPI Backend | http://localhost:8000 |
| FastAPI Docs (Swagger) | http://localhost:8000/docs |
| Flower (Celery Monitor) | http://localhost:5555 |

---

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 8501
netstat -ano | findstr :8501

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### Clear Streamlit Cache
```bash
uv run streamlit cache clear
```

### Check Streamlit Version
```bash
uv run streamlit version
```

---

## Environment Variables

Make sure your `.env` file has the required variables:
```env
# Required for Streamlit to connect to backend
BACKEND_URL=http://localhost:8000

# Optional Streamlit settings
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_HEADLESS=true
```

---

## Production Commands

### Run with All Production Settings
```bash
uv run streamlit run frontend/Home.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.fileWatcherType none \
    --browser.gatherUsageStats false
```

### Run in Background (Linux/Mac)
```bash
nohup uv run streamlit run frontend/Home.py &
```

### Run in Background (Windows PowerShell)
```powershell
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run", "streamlit", "run", "frontend/Home.py"
```
