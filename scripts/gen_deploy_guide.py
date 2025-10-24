import os
from datetime import datetime

DEPLOY_PATH = "docs/DEPLOY_GUIDE.md"

HEADER = f"""# 🚀 Deployment & Recovery Guide – vBoarder-Agno Stack

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Environment:** Ubuntu 24.04 WSL + Docker Compose
**Author:** Auto-generated via `gen_deploy_guide.py`

---
"""

CONTENT = """
## 🛠️ 1. Stack Components

- FastAPI -- REST API runtime on port `8000`
- Postgres + pgvector -- Vector DB on port `5432`
- Ollama -- Local LLM inference engine on port `11434`
- GPU -- RTX 3060 Ti (8 GB) for local model inference

---

## 🚀 2. Deployment Steps

Clone repo and spin it up:

    git clone <your-repo-url> vboarder-agno
    cd vboarder-agno
    docker-compose up -d
    make init-db

---

## 🔎 3. Service Health Checks

Check that services are responding:

    curl http://localhost:8000/docs
    docker exec -it pgvector psql -U ai -d ai -c "\\dt"
    curl http://localhost:11434/api/tags

Expected tables:

- `agno_sessions`
- `agno_memories`
- `agno_metrics`
- `agno_knowledge`
- `agno_evals`

---

## 🔄 4. Restart or Reset

To restart:

    docker-compose down
    docker-compose up -d

To reinit the DB (non-destructive):

    make init-db

---

## 💾 5. Persistent Assets

| Resource     | Path                          |
| ------------ | ----------------------------- |
| DB Volume    | `vboarder-agno-clean_pgvolume` |
| Model Store  | `ollama_data/`                |
| Ports        | 8000 (API), 5432 (DB), 11434 (Ollama) |

---

## 🧪 6. Tagging for Handoff

    git add docs scripts
    git commit -m "CTO handoff -- DB initialized and verified"
    git tag handoff-v2.1

---

## 🧰 7. Optional: Makefile Shortcuts

    make init-db
    make psql
    make status
    make deploy-guide

---
"""

def generate_guide():
    os.makedirs("docs", exist_ok=True)
    with open(DEPLOY_PATH, "w") as f:
        f.write(HEADER + CONTENT)
    print(f"✅ Deployment guide generated at {DEPLOY_PATH}")

if __name__ == "__main__":
    generate_guide()
