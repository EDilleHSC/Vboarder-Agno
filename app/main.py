import os

from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.models.ollama import Ollama
from agno.os import AgentOS

# Build the DSN manually — this works across all Agno builds.
# Environment variables are used to securely configure the database connection.
db_user = os.getenv("DB_USER", "ai")
db_password = os.getenv("DB_PASSWORD", "ai")
db_host = os.getenv("DB_HOST", "pgvector")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "ai")

db_connection_str = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# Initialize the Agent
agent = Agent(
    name="vboarder-agent",
    # Uses Ollama to connect to a local or networked llama3.1:8b model
    model=Ollama(id="llama3.1:8b"),
    # Connects to the PostgreSQL database for memory and state management
    # FIX: Changed from .from_url(...) to direct constructor call PostgresDb(...)
    db=PostgresDb(db_connection_str),
    # Enables history to be included in the context window for conversational memory
    add_history_to_context=True,
    # Ensures the output is formatted nicely
    markdown=True,
)

# Create the AgentOS application instance
app = AgentOS(agents=[agent]).get_app()

if __name__ == "__main__":
    # Runs the application server on the default host and port
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
