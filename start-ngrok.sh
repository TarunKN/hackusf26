#!/usr/bin/env bash
# start-ngrok.sh
# Starts the FormCoach API server and exposes it publicly via ngrok.
# Usage: bash start-ngrok.sh
#
# Prerequisites:
#   1. ngrok installed: https://ngrok.com/download
#      - Linux/WSL: curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
#                   echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
#                   sudo apt update && sudo apt install ngrok
#   2. ngrok authenticated: ngrok config add-authtoken <YOUR_TOKEN>
#      Get your token at: https://dashboard.ngrok.com/get-started/your-authtoken
#   3. Python deps installed: pip install -r requirements.txt
#   4. .env file configured with GEMINI_API_KEY

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT=8000

echo "============================================"
echo "  FormCoach — Starting with ngrok tunnel"
echo "============================================"

# Check .env exists
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and add your GEMINI_API_KEY."
  exit 1
fi

# Check ngrok is installed
if ! command -v ngrok &>/dev/null; then
  echo "ERROR: ngrok not found. Install it from https://ngrok.com/download"
  echo ""
  echo "Quick install (WSL/Linux):"
  echo "  curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null"
  echo "  echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | sudo tee /etc/apt/sources.list.d/ngrok.list"
  echo "  sudo apt update && sudo apt install ngrok"
  echo "  ngrok config add-authtoken <YOUR_TOKEN>"
  exit 1
fi

# Kill any existing server on port 8000
echo "Stopping any existing server on port $PORT..."
fuser -k ${PORT}/tcp 2>/dev/null || true

# Start the Python API server in the background
echo "Starting FormCoach API server on port $PORT..."
python api/main.py &
API_PID=$!

# Wait for server to be ready
echo "Waiting for server to start..."
for i in $(seq 1 20); do
  if curl -sf http://localhost:$PORT/health >/dev/null 2>&1; then
    echo "✓ Server is ready!"
    break
  fi
  sleep 1
done

# Start ngrok tunnel
echo ""
echo "Starting ngrok tunnel..."
echo "Your public URL will appear below. Share it with anyone!"
echo "The frontend is at: <ngrok-url>/ui/"
echo ""
echo "Press Ctrl+C to stop everything."
echo "============================================"

# Trap Ctrl+C to kill both processes
cleanup() {
  echo ""
  echo "Shutting down..."
  kill $API_PID 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# Start ngrok (this blocks until Ctrl+C)
ngrok http $PORT --log=stdout
