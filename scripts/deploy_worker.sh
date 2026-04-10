#!/bin/bash
# Deploy and start the worker service on remote GPU server
# Usage: ./scripts/deploy_worker.sh

set -e

WORKER_DIR="${WORKER_DIR:-~/multimodal-worker}"
WORKER_PORT="${WORKER_PORT:-8001}"

echo "Setting up worker in $WORKER_DIR..."
mkdir -p "$WORKER_DIR"

pip install fastapi uvicorn colpali-engine torch pillow

echo "Starting worker on port $WORKER_PORT..."
cd "$WORKER_DIR"
python -m uvicorn worker.main:app --host 0.0.0.0 --port "$WORKER_PORT"
