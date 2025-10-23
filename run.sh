#!/usr/bin/env bash
set -e

if command -v nvidia-smi &> /dev/null; then
  echo "✅ GPU detected — running in GPU mode..."
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
else
  echo "⚙️  No GPU detected — running in CPU mode..."
  docker compose up --build
fi
