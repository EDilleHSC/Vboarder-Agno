# agents/project_manager_agent.py
import os
import datetime
from agno.agent import Agent
from agno.tools.duckduckgo import DuckDuckGoTools
from dotenv import load_dotenv

# Import your local Ollama model
from agentos import CustomOllamaModel
from agents.maintenance_agent import maintenance_agent

load_dotenv()

project_root = "/mnt/d/ai/projects/vboarder-agno-clean"

# 🧠 The Project Manager Agent
project_manager_agent = Agent(
    name="Project Manager AI",
    model=CustomOllamaModel(id="llama3.2:3b"),
    tools=[DuckDuckGoTools(), maintenance_agent],
    instructions=[
        "You are the Project Manager and Engineering Assistant for the VBoarder project.",
        "Your mission is to keep the project clean, documented, and operational.",
        "Supervise all other agents (like maintenance or API agents).",
        "Ensure files are well-structured and updated.",
        "Generate daily and weekly project reports in /reports/executive/",
        "Use markdown formatting for all your responses."
    ],
    add_datetime_to_context=True,
    add_history_to_context=True,
    num_history_runs=10,
    markdown=True,
)

def run_project_manager():
    """Runs the AI project manager once manually."""
    print("🧩 Project Manager AI is reviewing the workspace...")
    report_dir = os.path.join(project_root, "reports", "executive")
    os.makedirs(report_dir, exist_ok=True)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    report_path = os.path.join(report_dir, f"project_review_{today}.md")

    summary = project_manager_agent.run(f"Analyze the current project structure at {project_root} and report health, missing files, and next steps.")

    with open(report_path, "w") as f:
        f.write(summary)

    print(f"✅ Report saved: {report_path}")

if __name__ == "__main__":
    run_project_manager()
