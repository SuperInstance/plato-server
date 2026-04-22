#!/bin/bash
set -e

echo "╔══════════════════════════════════════════╗"
echo "║  PLATO Knowledge System                  ║"
echo "║  Your own knowledge server. Ready.       ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Data: ${PLATO_DATA:-/data}"
echo "  Port: ${PLATO_PORT:-8847}"
echo "  Fleet sync: ${PLATO_FLEET_SYNC:-off}"
echo ""

exec python3 /app/server.py
