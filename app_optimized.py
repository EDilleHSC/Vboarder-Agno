"""FastAPI with /agents endpoint"""
import logging, os, time
from urllib.parse import urlparse
from agno.agent import Agent
from agno.db.postgres import PostgresDb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
log = logging.getLogger("agentos")

DB_CONNECTION_URL = os.getenv("DB_CONNECTION_URL", "postgresql://ai:ai@pgvector:5432/ai")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:latest")

db = None
try:
    url = urlparse(DB_CONNECTION_URL)
    log.info(f"📡 Database: {url.hostname}:{url.port}")
    for attempt in range(1, 11):
        try:
            db = PostgresDb(DB_CONNECTION_URL)
            log.info("✅ Connected to Postgres!")
            break
        except Exception as e:
            log.warning(f"⏳ Attempt {attempt}/10")
            if attempt < 10:
                time.sleep(3)
except Exception as e:
    log.error(f"❌ DB error: {e}")

agent = None
try:
    from agno.models.ollama import Ollama
    log.info(f"🧠 Ollama: {OLLAMA_MODEL}")
    agent = Agent(name="VBoarder", model=Ollama(id=OLLAMA_MODEL), db=db)
    log.info("✅ Agent ready")
except Exception as e:
    log.error(f"❌ Agent: {e}")

app = FastAPI(title="VBoarder API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

@app.get("/")
async def root():
    return {"status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "ready" if agent else "error"}

@app.get("/agents")
async def list_agents():
    return {"agents": [{"id": "default", "name": "VBoarder", "model": OLLAMA_MODEL, "status": "ready" if agent else "error"}], "total": 1}

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    if agent_id != "default":
        raise HTTPException(status_code=404, detail="Not found")
    return {"id": "default", "name": "VBoarder", "model": OLLAMA_MODEL, "status": "ready" if agent else "error"}

@app.post("/chat")
async def chat(request: Request):
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not ready")
    try:
        data = await request.json()
        msg = data.get("message", "")
        if not msg:
            raise HTTPException(status_code=400)
        response = agent.run(msg)
        return {"response": str(response), "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/{agent_id}/chat")
async def agent_chat(agent_id: str, request: Request):
    if agent_id != "default":
        raise HTTPException(status_code=404)
    if not agent:
        raise HTTPException(status_code=503)
    try:
        data = await request.json()
        msg = data.get("message", "")
        if not msg:
            raise HTTPException(status_code=400)
        response = agent.run(msg)
        return {"response": str(response), "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup():
    log.info("✅ API Started")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
