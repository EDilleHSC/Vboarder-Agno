#!/usr/bin/env bash
echo "🚀 vBoarder-Agno Model Sync — Future-Proof Edition"

models=(
  "trm:mini"
  "lfm:mini"
  "metamed:embed"
  "llama3"
  "phi3:mini"
  "mistral"
  "gemma3:4b"
  "granite3.3:2b"
  "qwen3:1.7b"
  "qwen3:4b"
  "deepseek-coder:6.7b"
  "embedding-gemma"
  "nomic-embed-text"
  "bge-base-en-v1.5"
  "tinyllama"
)

for model in "${models[@]}"; do
  echo "📥 Checking $model..."
  if docker exec vboarder_ollama ollama list | grep -q "$model"; then
    echo "✅ Already cached: $model"
  else
    echo "⬇️ Pulling $model..."
    docker exec vboarder_ollama ollama pull "$model" || echo "⚠️ Failed or not yet available: $model"
  fi
done

echo "✅ All available models pulled and cached in /mnt/d/ai/models/ollama"
