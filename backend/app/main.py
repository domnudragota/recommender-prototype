from fastapi import FastAPI
from backend.app.config import settings
from backend.app.logging_setup import setup_logging

setup_logging(settings.log_level)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }

@app.get("/")
def root():
    return {
        "message": "Recommender prototype API is running",
        "docs": "/docs",
        "health": "/health",
    }
