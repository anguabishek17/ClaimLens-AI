"""
ClaimLens AI — Application Entry Point
Problem: PS02 — Insurance Claims Evidence Review Assistant

Starts FastAPI backend and serves the frontend on http://localhost:8000.
"""

import sys
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.config import settings
from backend.routes import router as api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="PS02: Insurance Claims Evidence Review Assistant"
)

# 1. Mount API Router
app.include_router(api_router)

# 2. Serve Frontend Static Files
if settings.FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(settings.FRONTEND_DIR)), name="static")

    # Serve index.html at root
    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(settings.FRONTEND_DIR / "index.html")

    # Serve style.css directly at root level if requested
    @app.get("/style.css", include_in_schema=False)
    async def serve_css():
        return FileResponse(settings.FRONTEND_DIR / "style.css")

    # Serve app.js directly at root level if requested
    @app.get("/app.js", include_in_schema=False)
    async def serve_js():
        return FileResponse(settings.FRONTEND_DIR / "app.js")


if __name__ == "__main__":
    print(f"[*] Starting {settings.PROJECT_NAME} on http://localhost:{settings.PORT}")
    print(f"[*] Health Check: http://localhost:{settings.PORT}/api/health")
    print(f"[*] Frontend Dashboard: http://localhost:{settings.PORT}/")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG
    )

