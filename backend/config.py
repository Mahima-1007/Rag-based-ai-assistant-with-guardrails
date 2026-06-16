"""
config.py — Application settings loaded from .env
Uses Pydantic BaseSettings for type-safe environment variable parsing.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "RAG-AI-Assistant"
    APP_ENV: str = "development"
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # PostgreSQL
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_QUERY: int = 300
    CACHE_TTL_EMBEDDING: int = 3600
    CACHE_TTL_RETRIEVAL: int = 180
    CACHE_TTL_RESPONSE: int = 300

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""

    # Groq LLM
    GROQ_API_KEY: str
    GROQ_MODEL: str = "mixtral-8x7b-32768"
    GROQ_MAX_TOKENS: int = 2048
    GROQ_TEMPERATURE: float = 0.1

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # Chunking
    PARENT_CHUNK_SIZE: int = 1000
    PARENT_CHUNK_OVERLAP: int = 200
    CHILD_CHUNK_SIZE: int = 256
    CHILD_CHUNK_OVERLAP: int = 50

    # Retrieval
    RETRIEVAL_TOP_K: int = 20
    RERANKER_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.50
    CONFIDENCE_HIGH_THRESHOLD: float = 0.65
    CONFIDENCE_MEDIUM_THRESHOLD: float = 0.45

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
