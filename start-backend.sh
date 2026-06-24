#!/bin/bash
# YontAI Backend Launcher - Called by Tauri desktop app
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
BACKEND_DIR="$PROJECT_DIR/apps/backend"
cd "$BACKEND_DIR"

# Use project-level .venv first, then apps/backend/.venv
for VENV in "$PROJECT_DIR/.venv/bin/activate" "$BACKEND_DIR/.venv/bin/activate"; do
    if [ -f "$VENV" ]; then
        source "$VENV"
        break
    fi
done

# Start uvicorn
exec uvicorn yontai.main:app --host 127.0.0.1 --port 8765 --no-reload