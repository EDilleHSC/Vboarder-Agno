"""FastAPI with /agents and /chat endpoints - optimized and secured"""
import logging
import os
import time
from urllib.parse import urlparse

# Agno imports
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.ollama import Ollama
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# --------------------------------------------------------------------
# 🌍 Environment & Logging
# --------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
log = logging.getLogger("agentos")

DB_CONNECTION_URL = os.getenv("DB_CONNECTION_URL", "postgresql://ai:ai@pgvector:5432/ai")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:latest")
API_KEY = os.getenv("AGENT_API_KEY")  # Optional security token

# List of endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    "/health",           # Health check - Docker/K8s/monitoring
    "/",                 # Root
    "/connect",          # ✅ ADD THIS LINE - Agno discovery
    "/openapi.json",     # OpenAPI schema
    "/docs",             # Swagger UI
    "/redoc",            # ReDoc
]

# --------------------------------------------------------------------
# 🧠 Database setup
# --------------------------------------------------------------------
db = None
try:
    url = urlparse(DB_CONNECTION_URL)
    log.info(f"📡 Connecting to Postgres at {url.hostname}:{url.port}")
    for attempt in range(1, 11):
        try:
            db = PostgresDb(DB_CONNECTION_URL)
            log.info("✅ Connected to Postgres!")
            break
        except Exception as e:
            log.warning(f"⏳ DB connection attempt {attempt}/10 failed: {e}")
            if attempt < 10:
                time.sleep(3)
    if not db:
        raise Exception("Unable to connect to Postgres after multiple attempts.")
except Exception as e:
    log.error(f"❌ Database initialization error: {e}")

# --------------------------------------------------------------------
# 🤖 Agent setup
# --------------------------------------------------------------------
agent = None
try:
    log.info(f"🧠 Initializing Ollama model: {OLLAMA_MODEL}")
    agent = Agent(name="VBoarder", model=Ollama(id=OLLAMA_MODEL), db=db)
    log.info("✅ Agent ready")
except Exception as e:
    log.error(f"❌ Failed to initialize agent: {e}")

# --------------------------------------------------------------------
# 🚀 FastAPI setup
# --------------------------------------------------------------------
app = FastAPI(title="VBoarder API")

# Allow requests from local UI and cloud control plane
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can narrow this later
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# --------------------------------------------------------------------
# 🔒 Security Middleware
# --------------------------------------------------------------------
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    """
    Require authentication if AGENT_API_KEY is set.
    Supports both Bearer and X-API-Key headers.
    Public endpoints (health, docs, etc.) are exempt.
    """
    # ✅ Skip auth for public endpoints
    if request.url.path in PUBLIC_ENDPOINTS:
        return await call_next(request)

    # ✅ Skip auth if no API key is configured
    if not API_KEY:
        return await call_next(request)

    # Check Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
        if token == API_KEY:
            return await call_next(request)

    # Check X-API-Key header (alternative)
    api_key_header = request.headers.get("X-API-Key", "")
    if api_key_header == API_KEY:
        return await call_next(request)

    # No valid auth provided
    log.warning(f"🚨 Unauthorized access attempt to {request.url.path} from {request.client.host}")
    raise HTTPException(status_code=401, detail="Unauthorized - provide valid API key")


# --------------------------------------------------------------------
# 🌡️ Health & Metadata
# --------------------------------------------------------------------
@app.get("/")
async def root():
    """Root endpoint"""
    return {"status": "running", "service": "VBoarder API"}


@app.get("/health")
async def health():
    """
    Health check endpoint - no authentication required.
    Used by Docker, Kubernetes, and monitoring systems.
    """
    return {
        "status": "healthy",
        "agent": "ready" if agent else "error",
        "database": "ok" if db else "error",
    }


@app.get("/agents")
async def list_agents():
    """List all available agents"""
    return {
        "agents": [
            {
                "id": "default",
                "name": "VBoarder",
                "model": OLLAMA_MODEL,
                "status": "ready" if agent else "error",
            }
        ],
        "total": 1,
    }


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get details of a specific agent"""
    if agent_id != "default":
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "id": "default",
        "name": "VBoarder",
        "model": OLLAMA_MODEL,
        "status": "ready" if agent else "error",
    }


@app.get("/connect")
async def connect(request: Request):
    """Used by Agno Control Plane to verify connection + authentication"""
    client = request.client.host
    return {
        "status": "connected",
        "client": client,
        "agent": "VBoarder",
        "model": OLLAMA_MODEL,
        "secure": bool(API_KEY),
        "db": "ok" if db else "error",
    }


# --------------------------------------------------------------------
# 💬 Chat Endpoints
# --------------------------------------------------------------------
@app.post("/chat")
async def chat(request: Request):
    """
    Chat endpoint - send a message and get a response from the agent.
    Requires authentication if AGENT_API_KEY is set.
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    try:
        data = await request.json()
        msg = data.get("message", "").strip()
        if not msg:
            raise HTTPException(status_code=400, detail="Missing 'message'")

        log.info(f"💬 Processing chat message: {msg[:50]}...")
        response = agent.run(msg)

        return {
            "response": str(response),
            "status": "success",
            "agent": "VBoarder",
        }
    except Exception as e:
        log.exception("Error in /chat endpoint")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/chat")
async def agent_chat(agent_id: str, request: Request):
    """
    Agent-specific chat endpoint.
    Requires authentication if AGENT_API_KEY is set.
    """
    if agent_id != "default":
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")

    try:
        data = await request.json()
        msg = data.get("message", "").strip()
        if not msg:
            raise HTTPException(status_code=400, detail="Missing 'message'")

        log.info(f"💬 Processing agent chat message: {msg[:50]}...")
        response = agent.run(msg)

        return {
            "response": str(response),
            "status": "success",
            "agent": agent_id,
        }
    except Exception as e:
        log.exception(f"Error in /agents/{agent_id}/chat endpoint")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------
# ⚙️ Startup Event
# --------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    if API_KEY:
        log.info("🔒 API is running with authentication enabled")
    else:
        log.info("⚠️  API is running WITHOUT authentication (set AGENT_API_KEY for security)")
    log.info("✅ API Started successfully")


# --------------------------------------------------------------------
# 🏁 Entry Point
# --------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
