import os
import logging
import requests
from typing import Optional, AsyncGenerator
from dotenv import load_dotenv

from agno.agent import Agent
from agno.models.base import Model
from agno.os import AgentOS
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from agno.vectordb.pgvector import PgVector
from local_embedder import LocalOllamaEmbedder as OllamaEmbedder



# =============================================================================
# 🔧 SETUP & LOGGING
# =============================================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
)
logger = logging.getLogger("AgentOS")

# Auto-detect host (for WSL vs Docker)
ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
if "ollama" in ollama_host and not os.path.exists("/.dockerenv"):
    # We're not in Docker → switch to localhost automatically
    ollama_host = "http://localhost:11434"
    os.environ["OLLAMA_HOST"] = ollama_host
    logger.info(f"🔁 Auto-switched OLLAMA_HOST to local: {ollama_host}")


# =============================================================================
# 🔍 CONFIG VALIDATION
# =============================================================================
def validate_configuration():
    """Ensure required services and environment variables are available."""
    logger.info("🔍 Validating environment configuration...")

    db_url = os.getenv("DB_CONNECTION_URL")
    if not db_url:
        raise SystemExit("❌ Missing DB_CONNECTION_URL in .env or environment")

    try:
        logger.info(f"🔗 Checking Ollama connectivity at {ollama_host}...")
        res = requests.get(f"{ollama_host}/api/tags", timeout=5)
        if res.status_code == 200:
            logger.info("✅ Ollama is reachable")
        else:
            logger.warning(f"⚠️ Ollama responded with status {res.status_code}")
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"❌ Ollama not reachable at {ollama_host}: {e}")

    logger.info("✅ Configuration check passed")


# =============================================================================
# 🤖 CUSTOM MODEL
# =============================================================================
class CustomOllamaModel(Model):
    """Bridge between Agno and local Ollama instance."""

    def __init__(
        self,
        id: str = "llama3.2:3b",
        host: Optional[str] = None,
        timeout: int = 60,
        **kwargs
    ):
        self.id = id
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.timeout = timeout
        super().__init__(id=id, **kwargs)
        logger.info(f"✅ CustomOllamaModel ready: {self.id} @ {self.host}")

    def invoke(self, prompt: str, **kwargs) -> str:
        """Send prompt to Ollama and return the response."""
        try:
            res = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.id, "prompt": prompt, "stream": False},
                timeout=self.timeout,
            )
            res.raise_for_status()
            output = res.json().get("response", "").strip()
            return output or "[⚠️ Empty model response]"
        except requests.exceptions.Timeout:
            return f"[❌ Timeout after {self.timeout}s]"
        except requests.exceptions.ConnectionError:
            return f"[❌ Cannot reach Ollama at {self.host}]"
        except Exception as e:
            return f"[💥 Unexpected error: {e}]"

    async def ainvoke(self, prompt: str, **kwargs) -> str:
        return self.invoke(prompt, **kwargs)

    def invoke_stream(self, prompt: str, **kwargs):
        raise NotImplementedError("Streaming not yet implemented.")

    async def ainvoke_stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        raise NotImplementedError("Async streaming not yet implemented.")

    def _parse_provider_response(self, response: dict) -> str:
        return response.get("response", "")

    def _parse_provider_response_delta(self, delta: dict) -> str:
        return delta.get("response", "")


# =============================================================================
# 🧠 DATABASE CONNECTION (LOCAL EMBEDDER)
# =============================================================================
def create_db_connection():
    """Connect to PgVector database using a local Ollama embedder."""
    db_url = os.getenv("DB_CONNECTION_URL")
    db_table = os.getenv("DB_TABLE", "agno_memories")
    db_schema = os.getenv("DB_SCHEMA", "ai")

    try:
        # Use local nomic-embed-text for embeddings
        embedder = OllamaEmbedder(
            model="nomic-embed-text",
            host=ollama_host,
        )

        db = PgVector(
            db_url=db_url,
            table_name=db_table,
            schema=db_schema,
            embedder=embedder,
        )

        logger.info(f"✅ Connected PgVector DB ({db_schema}.{db_table}) with local embedder (nomic-embed-text)")
        return db
    except Exception as e:
        raise SystemExit(f"❌ Database connection failed: {e}")


# =============================================================================
# 🧩 AGENT CREATION
# =============================================================================
def create_agent(db):
    """Instantiate and configure the main agent."""
    return Agent(
        name="Docker Dev Agent",
        model=CustomOllamaModel(id="llama3.2:3b"),
        tools=[DuckDuckGoTools(), YFinanceTools()],
        db=db,
        instructions=[
            "You are a full-stack assistant focused on precision and clarity.",
            "Use markdown formatting for readability.",
            "Cite sources when using external tools.",
            "If errors occur, explain them clearly and suggest fixes.",
        ],
        add_datetime_to_context=True,
        add_history_to_context=True,
        num_history_runs=5,
        markdown=True,
    )


# =============================================================================
# 🚀 MAIN ENTRYPOINT
# =============================================================================
app = None  # 🔧 Define globally so Uvicorn can find it


def main():
    global app  # 🔧 Required to make it visible at module scope
    print("\n" + "=" * 70)
    print("🤖  AGNO AGENTOS STARTUP")
    print("=" * 70)

    try:
        validate_configuration()
        db = create_db_connection()
        agent = create_agent(db)

        agent_os = AgentOS(agents=[agent])
        app = agent_os.get_app()  # 🔧 Assign FastAPI app at global level

        logger.info("✅ AgentOS initialized successfully")
        logger.info("🌐 Running at http://0.0.0.0:8000")

        agent_os.serve("agentos:app", reload=True, port=8000, host="0.0.0.0")
    except Exception as e:
        logger.critical(f"💥 Startup failure: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
