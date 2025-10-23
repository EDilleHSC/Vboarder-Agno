import asyncio
import logging
import os
import time
from urllib.parse import urlparse

import httpx
import psycopg2  # Used for database health check
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from dotenv import load_dotenv
from fastapi import FastAPI, Query, status
from fastapi.responses import JSONResponse, RedirectResponse

# ---------------------------------------------------------------------
# Environment & Logging Setup
# ---------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("agentos")

# ---------------------------------------------------------------------
# Database Setup (with Retry Logic)
# ---------------------------------------------------------------------
db = None
max_retries = 10
retry_delay = 3

DB_CONNECTION_URL = os.getenv(
    "DB_CONNECTION_URL", "postgresql://ai:ai@pgvector:5432/ai"
)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

try:
    url = urlparse(DB_CONNECTION_URL)
    log.info(f"📡 Parsed DB connection: {url.hostname}:{url.port}/{url.path.lstrip('/')}")

    for attempt in range(1, max_retries + 1):
        try:
            db = PostgresDb(DB_CONNECTION_URL)  # connects on init
            log.info("✅ Successfully connected to Postgres!")
            break
        except Exception as e:
            log.warning(f"⏳ Attempt {attempt}/{max_retries} failed: {e}")
            time.sleep(retry_delay)
    else:
        log.error("❌ Could not connect to Postgres after multiple attempts.")
        db = None

except Exception as e:
    log.critical(f"FATAL: Database setup failed: {e}")
    db = None


# ---------------------------------------------------------------------
# Agent Setup (Ollama-compatible across Agno versions)
# ---------------------------------------------------------------------
ollama_model = None
try:
    # Try the newest import path first
    from agno.models.ollama import OllamaModel
    ollama_model = OllamaModel("mistral")
    log.info("🧠 Using OllamaModel (new API).")
except ImportError:
    try:
        from agno.models.ollama import Ollama
        ollama_model = Ollama("mistral")
        log.info("🧠 Using Ollama (legacy API).")
    except Exception as e:
        log.error(f"❌ Could not initialize Ollama model: {e}")

# Create the Agent if possible
agent = Agent(db=db, model=ollama_model) if ollama_model else None


# ---------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------
app = FastAPI(
    title="AgentOS API",
    description="AI Agent Operating System API",
    version="1.0.0",
)


@app.get("/")
def root():
    """Redirect root to Swagger docs for convenience."""
    return RedirectResponse("/docs")


# ---------------------------------------------------------------------
# Health & Readiness Endpoints
# ---------------------------------------------------------------------
async def check_db() -> bool:
    """Run SELECT 1 against Postgres safely in a thread (asyncio.to_thread fix)."""
    def _check():
        try:
            # psycopg2 is imported at the top of the file
            conn = psycopg2.connect(DB_CONNECTION_URL)
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            conn.close()
            return True
        except Exception as e:
            log.error(f"❌ Database health check failed: {e}")
            return False

    return await asyncio.to_thread(_check)


async def check_ollama() -> bool:
    """Ping Ollama /api/tags endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            return resp.status_code == 200
    except Exception as e:
        log.error(f"❌ Ollama health check failed: {e}")
        return False


@app.get("/health", status_code=status.HTTP_200_OK)
async def health():
    """Standard health endpoint."""
    log.info("---- /health called ----")
    db_ok, ollama_ok = await asyncio.gather(check_db(), check_ollama())

    if not db_ok and not ollama_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"db": "fail", "ollama": "fail"},
        )

    return {"db": "ok" if db_ok else "fail", "ollama": "ok" if ollama_ok else "fail"}


@app.get("/ready", status_code=status.HTTP_200_OK)
async def ready():
    """Readiness probe for Docker/K8s healthchecks."""
    db_ok, ollama_ok = await asyncio.gather(check_db(), check_ollama())
    return {"ready": db_ok and ollama_ok}


# ---------------------------------------------------------------------
# Agent Endpoint (SDK-version safe)
# ---------------------------------------------------------------------
@app.get("/ask")
async def ask(question: str = Query(..., min_length=1, description="User question")):
    """Handles agent queries."""
    if not db or not agent:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Agent not initialized. Check database connection or model setup."},
        )

    try:
        # Handle differences in SDK method names
        if hasattr(agent, "chat"):
            response = await agent.chat(question)
        elif hasattr(agent, "run"):
            response = await agent.run(question)
        else:
            # Fallback to the original method name 'ask' if neither 'chat' nor 'run' is available
            response = await agent.ask(question)

        return {"answer": response}

    except Exception as e:
        log.error(f"❌ Agent processing failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Agent processing failed: {str(e)}"},
        )
