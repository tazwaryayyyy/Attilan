from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.database import db_manager
from backend.app.routers import entity, events, export, ingest


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Lifespan startup
    try:
        await db_manager.connect()
    except Exception as e:
        # Allow running in testing/offline mock environments
        print(f"Warning: Database connection could not be established on startup: {e}")
    yield
    # Lifespan shutdown
    await db_manager.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Criminal Intelligence & Evidence Integrity Platform (Evidence Act 2022 Compliant)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(entity.router)
app.include_router(events.router)
app.include_router(export.router)


@app.get("/health", tags=["System Health"])
async def health_check():
    return {
        "status": "OPERATIONAL",
        "platform": settings.PROJECT_NAME,
        "compliance": "Evidence (Amendment) Act 2022 s.65B",
        "storage": "MinIO WORM (Object Lock Enabled)",
    }
