"""
The FastAPI app: creates the app, sets up logging and defines the routes.

Run it from the backend/ folder with:  uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import config
from app.db import get_db, init_db

# Set up logging ONCE for the whole app. Every log line looks like:
# 2026-11-07 10:00:00,123 | INFO | groq_client | LLM call ok | ...
logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(module)s | %(message)s",
)
logger = logging.getLogger(__name__)


# lifespan = code that runs when the server starts and when it stops.
# Everything BEFORE `yield` runs once at startup; everything AFTER runs at shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create the tables if they don't exist yet
    logger.info("Startup complete | database ready | llm_model=%s", config.LLM_MODEL)
    yield
    logger.info("Shutting down")


app = FastAPI(title="RepoViva API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Is the server up, and can it reach the database?

    Depends(get_db): before this function runs, FastAPI calls get_db() and passes
    the session it yields in as `db`. After the response, get_db closes it."""
    try:
        db.execute(text("SELECT 1"))  # the smallest possible query: proves the DB answers
    except Exception:
        logger.exception("Health check failed: database is not reachable")
        # 503 = "Service Unavailable": the server is running but can't do its job right now.
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "unreachable",
                "llm_model": config.LLM_MODEL,
                "groq_key_set": bool(config.GROQ_API_KEY),
            },
        )

    return {
        "status": "ok",
        "database": "ok",
        "llm_model": config.LLM_MODEL,
        # Only True/False. Never send the key itself.
        "groq_key_set": bool(config.GROQ_API_KEY),
    }
