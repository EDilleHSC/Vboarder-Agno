import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
import psycopg2
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from dotenv import load_dotenv
from fastapi import FastAPI, Query, status, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

# =====================================================================
# Environment & Logging Setup
# =====================================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger("agentos")

# =====================================================================
# Configuration
# =====================================================================
DB_CONNECTION_URL = os.getenv(
    "DB_CONNECTION_URL", "postgresql://ai:ai@pgvector:5432/ai"
)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
API_KEY = os.getenv("API_KEY")  # Optional API key for security
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "30"))  # seconds
HEALTH_CHECK_CACHE_TTL = int(os.getenv("HEALTH_CHECK_CACHE_TTL", "5"))  # seconds

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# =====================================================================
# Cache for Health Checks (avoid repeated DB connections)
# =====================================================================
class HealthCache:
    def __init__(self, ttl: int = 5):
        self.ttl = ttl
        self.db_result = None
        self.db_timestamp = None
        self.ollama_result = None
        self.ollama_timestamp = None

    def get_db(self) -> tuple[bool | None, bool]:
        """Returns (cached_result, is_valid)"""
        if self.db_result is not None and self.db_timestamp:
            age = (datetime.now() - self.db_timestamp).total_seconds()
            if age < self.ttl:
                return self.db_result, True
        return None, False

    def set_db(self, result: bool):
        self.db_result = result
        self.db_timestamp = datetime.now()

    def get_ollama(self) -> tuple[bool | None, bool]:
        """Returns (cached_result, is_valid)"""
        if self.ollama_result is not None and self.ollama_timestamp:
            age = (datetime.now() - self.ollama_timestamp).total_seconds()
            if age < self.ttl:
                return self.ollama_result, True
        return None, False

    def set_ollama(self, result: bool):
        self.ollama_result = result
        self.ollama_timestamp = datetime.now()


health_cache = HealthCache(ttl=HEALTH_CHECK_CACHE_TTL)

# =====================================================================
# Database Setup (with Retry Logic)
# =====================================================================
db = None
max_retries = 10
retry_delay = 3

try:
    url = urlparse(DB_CONNECTION_URL)
    # Log safely without exposing credentials
    log.info(f"📡 Database: {url.hostname}:{url.port}")

    for attempt in range(1, max_retries + 1):
        try:
            db = PostgresDb(DB_CONNECTION_URL)
            log.info("✅ Successfully connected to Postgres!")
            break
        except Exception as e:
            log.warning(f"⏳ Connection attempt {attempt}/{max_retries} failed")
            if attempt < max_retries:
                time.sleep(retry_delay)
    else:
        log.error("❌ Could not connect to Postgres after multiple attempts")
        db = None

except Exception as e:
    log.critical(f"FATAL: Database setup failed: {type(e).__name__}")
    db = None

# =====================================================================
# Agent Setup (Ollama-compatible across Agno versions)
# =====================================================================
ollama_model = None
try:
    # Try the newest import path first
    from agno.models.ollama import OllamaModel

    ollama_model = OllamaModel("mistral")
    log.info("🧠 Using OllamaModel (new API)")
except ImportError:
    try:
        from agno.models.ollama import Ollama

        ollama_model = Ollama("mistral")
        log.info("🧠 Using Ollama (legacy API)")
    except Exception as e:
        log.error(f"❌ Could not initialize Ollama model: {type(e).__name__}")

# Create the Agent if possible
agent = Agent(db=db, model=ollama_model) if ollama_model else None

if agent:
    log.info("✅ Agent initialized successfully")
else:
    log.warning("⚠️ Agent not initialized - check Ollama and database connections")

# =====================================================================
# FastAPI App with Security Middleware
# =====================================================================
app = FastAPI(
    title="AgentOS API",
    description="AI Agent Operating System API",
    version="1.0.0",
)

# Add security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter

# =====================================================================
# Authentication & Authorization
# =====================================================================
async def verify_api_key(x_api_key: str = Header(None)) -> str:
    """Verify API key if configured. Pass None to disable auth."""
    if not API_KEY:
        return None  # No auth required

    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


# =====================================================================
# Routes
# =====================================================================
@app.get("/")
def root():
    """Redirect root to Swagger docs."""
    return RedirectResponse(url="/docs")


# =====================================================================
# Health & Readiness Endpoints
# =====================================================================
async def check_db() -> bool:
    """
    Check PostgreSQL connectivity safely in a thread.
    Uses cache to avoid excessive database hits.
    """
    cached, is_valid = health_cache.get_db()
    if is_valid:
        return cached

    def _check():
        try:
            conn = psycopg2.connect(DB_CONNECTION_URL)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            return True
        except Exception as e:
            log.error(f"Database health check failed: {type(e).__name__}")
            return False

    result = await asyncio.to_thread(_check)
    health_cache.set_db(result)
    return result


async def check_ollama() -> bool:
    """
    Ping Ollama /api/tags endpoint.
    Uses cache to avoid excessive requests.
    """
    cached, is_valid = health_cache.get_ollama()
    if is_valid:
        return cached

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            result = resp.status_code == 200
    except Exception as e:
        log.error(f"Ollama health check failed: {type(e).__name__}")
        result = False

    health_cache.set_ollama(result)
    return result


@app.get("/health", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def health(request: Request):
    """Standard health endpoint for monitoring."""
    log.debug("Health check requested")
    db_ok, ollama_ok = await asyncio.gather(check_db(), check_ollama())

    response_body = {"db": "ok" if db_ok else "fail", "ollama": "ok" if ollama_ok else "fail"}

    # Return 503 only if both are down
    status_code = (
        status.HTTP_503_SERVICE_UNAVAILABLE if (not db_ok and not ollama_ok) else status.HTTP_200_OK
    )

    return JSONResponse(status_code=status_code, content=response_body)


@app.get("/ready", status_code=status.HTTP_200_OK)
@limiter.limit("60/minute")
async def ready(request: Request):
    """Readiness probe for Kubernetes/Docker."""
    db_ok, ollama_ok = await asyncio.gather(check_db(), check_ollama())
    is_ready = db_ok and ollama_ok

    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"ready": False}
        )
    return {"ready": True}


# =====================================================================
# Agent Endpoint with Enhanced Security & Error Handling
# =====================================================================
@app.post("/ask")
@limiter.limit("30/minute")
async def ask(
    request: Request,
    question: str = Query(..., min_length=1, max_length=2000, description="User question"),
    api_key: str = Depends(verify_api_key),
):
    """
    Process a question through the AI agent.

    Rate limited to 30 requests per minute.
    Requires API_KEY header if API_KEY environment variable is set.
    """
    if not db or not agent:
        log.warning("Ask endpoint called but agent not initialized")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "Agent not initialized",
                "details": "Database or model unavailable"
            },
        )

    try:
        log.info(f"Processing question: {question[:100]}...")  # Log first 100 chars

        # Determine which method to use and wrap if needed
        if hasattr(agent, "chat"):
            response = agent.chat(question)
        elif hasattr(agent, "run"):
            response = agent.run(question)
        else:
            response = agent.ask(question)

        # Handle async responses (wrap in asyncio.to_thread if needed)
        if asyncio.iscoroutine(response):
            response = await response

        # Apply timeout protection
        try:
            response = await asyncio.wait_for(
                asyncio.create_task(_ensure_coroutine(response)),
                timeout=AGENT_TIMEOUT
            )
        except asyncio.TimeoutError:
            log.error("Agent processing timed out")
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={"error": "Agent processing timed out", "timeout": AGENT_TIMEOUT}
            )

        log.info("Question processed successfully")
        return {"answer": response}

    except HTTPException:
        raise  # Re-raise HTTP exceptions (like auth failures)
    except Exception as e:
        log.error(f"Agent processing failed: {type(e).__name__}: {str(e)[:200]}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Agent processing failed", "type": type(e).__name__},
        )


async def _ensure_coroutine(value):
    """Ensure a value is awaitable, even if it's a plain value."""
    if asyncio.iscoroutine(value):
        return await value
    return value


# =====================================================================
# Graceful Shutdown
# =====================================================================
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    log.info("Shutting down...")
    if db:
        try:
            # Close database connection if available
            if hasattr(db, "close"):
                db.close()
            log.info("✅ Database connection closed")
        except Exception as e:
            log.error(f"Error closing database: {type(e).__name__}")


# =====================================================================
# Startup Event
# =====================================================================
@app.on_event("startup")
async def startup_event():
    """Log startup info."""
    auth_enabled = "✅ Enabled" if API_KEY else "❌ Disabled"
    log.info(f"🚀 AgentOS API starting...")
    log.info(f"   Database: {'✅' if db else '❌'}")
    log.info(f"   Ollama: {'✅' if ollama_model else '❌'}")
    log.info(f"   Agent: {'✅' if agent else '❌'}")
    log.info(f"   API Auth: {auth_enabled}")
    log.info(f"   Agent Timeout: {AGENT_TIMEOUT}s")
