import os
import shutil
import subprocess
import datetime
from pathlib import Path
from agno.agent import Agent
from agno.tools.duckduckgo import DuckDuckGoTools
from dotenv import load_dotenv

# 🧠 Import your local Ollama model from agentos.py
from agentos import CustomOllamaModel

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports" / "daily"
VENV_PATH = BASE_DIR / ".venv-wsl"
REQUIREMENTS = BASE_DIR / "app" / "requirements.txt"

load_dotenv()


# === (Same cleaning + health functions as before) ===
# keep clean_pycache(), clean_logs(), check_dependencies(), etc. as they were


# 🧠 Local Maintenance Agent — uses Ollama instead of OpenAI
maintenance_agent = Agent(
    name="Local Maintenance Agent",
    model=CustomOllamaModel(id="llama3.2:3b"),
    tools=[DuckDuckGoTools()],
    instructions=[
        "You are a system maintenance and monitoring agent.",
        "Keep the local AI project environment clean, organized, and functional.",
        "Run diagnostics on the database, models, and code health.",
        "Always use markdown for reports and summarize key results clearly."
    ]
)
