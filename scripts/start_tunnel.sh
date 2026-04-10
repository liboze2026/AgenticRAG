#!/bin/bash
# Start SSH tunnel to remote GPU server via bastion host
# Usage: ./scripts/start_tunnel.sh

PEM_PATH="${PEM_PATH:-~/.ssh/key.pem}"
BASTION="${BASTION:-user@bastion-host}"
TARGET="${TARGET:-user@gpu-server}"
WORKER_PORT="${WORKER_PORT:-8001}"
QDRANT_PORT="${QDRANT_PORT:-6333}"

echo "Starting SSH tunnel..."
echo "  Bastion: $BASTION"
echo "  Target:  $TARGET"
echo "  Ports:   localhost:$WORKER_PORT -> remote:$WORKER_PORT"
echo "           localhost:$QDRANT_PORT -> remote:$QDRANT_PORT"

ssh -i "$PEM_PATH" -J "$BASTION" "$TARGET" \
    -L "$WORKER_PORT:localhost:$WORKER_PORT" \
    -L "$QDRANT_PORT:localhost:$QDRANT_PORT" \
    -N -o ServerAliveInterval=60 -o ServerAliveCountMax=3
