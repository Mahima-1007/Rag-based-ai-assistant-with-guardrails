"""
main.py — FastAPI application entry point.

Wires together:
  - All routers (auth, documents, chat)
  - CORS middleware
  - Startup: DB table creation, model preloading
  - Health check endpoint
  - Structured logging configuration
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from chat.router import router as chat_router
from config import get_settings
from database import create_tables
from documents.router import router as documents_router
from monitoring.logger import configure_logging, get_logger

settings = get_settings()
configure_logging(log_level="DEBUG" if settings.APP_ENV == "development" else "INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    logger.info("Starting RAG AI Assistant", env=settings.APP_ENV)

    # Create all PostgreSQL tables
    await create_tables()
    logger.info("Database tables verified")

    # Preload heavy ML models in background to avoid cold-start latency
    loop = asyncio.get_event_loop()

    def preload_models():
        from documents.embedding import get_embedding_model
        from retrieval.reranking import get_reranker
        from guardrails.presidio_service import get_analyzer, get_anonymizer
        get_embedding_model()
        get_reranker()
        get_analyzer()
        get_anonymizer()
        logger.info("All ML models preloaded")

    await loop.run_in_executor(None, preload_models)

    # Verify Redis connection
    from cache.redis_client import ping_redis
    redis_ok = await ping_redis()
    logger.info("Redis connection", status="ok" if redis_ok else "failed")

    yield

    logger.info("Shutting down RAG AI Assistant")


app = FastAPI(
    title="RAG AI Assistant API",
    description="Production-grade Document-Based RAG AI Assistant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(chat_router)


# ── Health Check ─────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    from cache.redis_client import ping_redis
    redis_ok = await ping_redis()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "redis": "connected" if redis_ok else "disconnected",
    }


@app.get("/", tags=["System"])
async def root():
    return {"message": "RAG AI Assistant API", "docs": "/docs"}
