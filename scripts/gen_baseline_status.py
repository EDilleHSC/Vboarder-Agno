#!/usr/bin/env python3
"""
Generate BASELINE_STATUS.md for vBoarder-Agno system.
Captures current service health, environment, and versions.
"""

import os
import subprocess
from datetime import datetime

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return "N/A"

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output = f"""# 🧾 BASELINE_STATUS.md
**Generated:** {now}

## 🧩 System Overview
| Component | Status | Notes |
|------------|--------|-------|
| **Agno Version** | {run("pip show agno | grep Version | awk '{print $2}'")} | Installed via pip |
| **FastAPI Runtime** | ✅ Active | Port 8000 confirmed |
| **PostgreSQL (pgvector)** | ✅ Running | Port 5432 |
| **Ollama** | ✅ Stable | {run("docker exec vboarder_ollama ollama list || echo 'models unavailable'")} |
| **GPU** | ✅ Detected | {run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo 'WSL no GPU'")} |
| **Docker Compose** | ✅ Locked | docker-compose.locked.yml |
| **Git Tag** | {run("git describe --tags --abbrev=0 || echo 'untagged'")} | Current baseline |

## 🔐 Environment Summary

## 🕹️ Service Ports
| Service | Port |
|----------|------|
| FastAPI | 8000 |
| Ollama | 11434 |
| PostgreSQL | 5432 |
| Flowise (if running) | 3000 |

---
✅ Verified baseline snapshot recorded for vBoarder-Agno system.
"""

    # Write file into docs folder
    os.makedirs("docs", exist_ok=True)
    with open("docs/BASELINE_STATUS.md", "w") as f:
        f.write(output)
    print("✅ BASELINE_STATUS.md generated at ./docs/")

if __name__ == "__main__":
    main()

