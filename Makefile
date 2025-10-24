# ──────────────────────────────────────────────
# vBoarder-Agno Stack – Local Dev Commands
# ──────────────────────────────────────────────

init-db:
	python3 scripts/init_agno_db.py

psql:
	docker exec -it pgvector psql -U ai -d ai

status:
	curl -s http://localhost:8000/docs > /dev/null && echo "✅ API running on :8000" || echo "❌ API not responding"
	docker exec -it pgvector psql -U ai -d ai -c "\dt"
	curl -s http://localhost:11434/api/tags | jq '.models[].name'

deploy-guide:
	python3 scripts/gen_deploy_guide.py
