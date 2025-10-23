import logging
import os
import re
import warnings

import uvicorn
from agno.agent import Agent
from agno.knowledge.embedder.ollama import OllamaEmbedder
from agno.models.ollama import Ollama
from agno.vectordb.pgvector.pgvector import PgVector
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings


# ─────────────────────────────
# Configuration
# ─────────────────────────────
class Settings(BaseSettings):
    """Centralized configuration for vBoarder Agno setup."""
    model_config = ConfigDict(env_file=".env", extra="ignore")

    DB_HOST: str = "pgvector"
    DB_PORT: str = "5432"
    DB_USER: str = "ai"
    DB_PASS: str = "ai"
    DB_DATABASE: str = "ai"

    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    AGENT_NAME: str = "LocalLlamaAgent"
    PORT: int = 9000


settings = Settings()


# ─────────────────────────────
# Normalize Ollama URL
# ─────────────────────────────
def normalize_ollama_url(url: str) -> str:
    if not re.match(r"^https?://", url):
        url = f"http://{url}"
    return url.rstrip("/")


OLLAMA_URL = normalize_ollama_url(settings.OLLAMA_HOST)
os.environ["OLLAMA_HOST"] = OLLAMA_URL  # for agno internals

DATABASE_URL = (
    f"postgresql://{settings.DB_USER}:{settings.DB_PASS}@"
    f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_DATABASE}"
)


# ─────────────────────────────
# Logging setup
# ─────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("vboarder-agent")

warnings.filterwarnings("ignore", message="Only Ollama v0.3.x and above are supported")

logger.info("🚀 Starting Agent Runner...")
logger.info(f"📡 Database: {DATABASE_URL}")
logger.info(f"🧠 Ollama Host: {OLLAMA_URL}")
logger.info(f"🤖 Model: {settings.OLLAMA_MODEL}")


# ─────────────────────────────
# Initialize components
# ─────────────────────────────
try:
    logger.info("🧩 Initializing Ollama + Embedder using 'host' parameter")

    llm = Ollama(id=settings.OLLAMA_MODEL, host=OLLAMA_URL)
    embedder = OllamaEmbedder(id=settings.OLLAMA_MODEL, host=OLLAMA_URL)

    memory = PgVector(
        db_url=DATABASE_URL,
        table_name="agent_memory",
        embedder=embedder,
    )

    agent = Agent(
        name=settings.AGENT_NAME,
        model=llm,
        db=None,
        enable_user_memories=False,  # optional: enable if you want persistent memory
    )
    agent.memory = memory

    logger.info("✅ Agent, memory, and embedder initialized successfully.")
except Exception:
    logger.exception("❌ Initialization failed. Check database and Ollama services.")
    raise SystemExit(1)


# ─────────────────────────────
# FastAPI App
# ─────────────────────────────
app = FastAPI(
    title="vBoarder Agno Agent",
    description="API for running the Agno-based AI agent with Ollama + pgvector.",
)


class AgentRunRequest(BaseModel):
    prompt: str


@app.get("/")
def root():
    return {"message": "Welcome to vBoarder Agno Agent", "endpoints": ["/health", "/run"]}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "agent": settings.AGENT_NAME,
        "model": settings.OLLAMA_MODEL,
        "ollama_host": OLLAMA_URL,
        "memory_type": "PgVector",
    }


@app.post("/run")
def run_agent(request: AgentRunRequest):
    try:
        result = agent.run(request.prompt)
        # Agno v2: result.output replaces result.output_text
        output_text = getattr(result, "output", str(result))
        short_output = (output_text or "").replace("\n", " ")[:120]
        logger.info(f"🗣️ Prompt: {request.prompt} → 💬 {short_output}...")
        return {"response": output_text}
    except Exception as e:
        logger.exception("❌ Agent execution failed:")
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")


# ─────────────────────────────
# Entry point
# ─────────────────────────────
if __name__ == "__main__":
    logger.info(f"🌐 Serving API at http://0.0.0.0:{settings.PORT}")
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT, reload=False, log_level="info")
