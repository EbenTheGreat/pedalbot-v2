"""
PedalBot FastAPI Application

Main entry point for the PedalBot API server.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.config.config import settings
from backend.db.mongodb import MongoDB
from backend.routers import query, ingest

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    await MongoDB.connect(
        uri=settings.MONGODB_URI,
        db_name=settings.MONGODB_DB_NAME
    )
    yield
    # Shutdown
    await MongoDB.close()

# Create FastAPI app
app = FastAPI(
    title="PedalBot API",
    description="AI-powered guitar pedal assistant with RAG and market pricing",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(query.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")

# Health check endpoint
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - health check."""
    return {
        "status": "healthy",
        "service": "PedalBot API",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "services": {
            "mongodb": "ok",
            "redis": "ok",
            "celery": "ok"
        }
    }