"""
main.py – FastAPI application entry-point.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import check_connection, create_tables
from app.routes import comparison as comparison_router
from app.routes import upload as upload_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Insurance Policy Comparator",
    description=(
        "REST API for uploading two insurance-policy PDFs and receiving "
        "a structured side-by-side comparison of coverage, exclusions, "
        "and premiums."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup() -> None:
    os.makedirs(settings.upload_path, exist_ok=True)
    logger.info("Upload directory: %s", settings.upload_path)

    if not check_connection():
        logger.critical(
            "Cannot connect to the database (%s). "
            "Please check your DATABASE_URL in .env",
            settings.DATABASE_URL,
        )
    else:
        create_tables()
        logger.info("Database ready.")


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(upload_router.router, prefix="/api", tags=["Upload & Compare"])
app.include_router(comparison_router.router, prefix="/api", tags=["Comparisons & History"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"], summary="Server health check")
async def health_check():
    db_ok = check_connection()
    return JSONResponse(
        content={
            "status": "healthy" if db_ok else "degraded",
            "database": "connected" if db_ok else "unreachable",
            "version": "1.0.0",
        },
        status_code=200 if db_ok else 503,
    )


@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    return {"message": "Insurance Policy Comparator API – see /docs for usage."}
