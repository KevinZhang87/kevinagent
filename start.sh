#!/bin/bash
echo "============================================"
echo "  KevinAgent"
echo "============================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python &> /dev/null; then
    echo "[ERROR] Python is not installed"
    exit 1
fi

# Check Node
if ! command -v node &> /dev/null; then
    echo "[ERROR] Node.js is not installed"
    exit 1
fi

# Install backend dependencies only if needed
if [ ! -f "backend/.deps_installed" ]; then
    echo "[1/3] Installing Python dependencies..."
    cd backend
    pip install -r requirements.txt -q
    touch .deps_installed
    cd ..
else
    echo "[1/3] Python dependencies already installed. Skipping."
fi

# Install frontend dependencies only if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "[2/3] Installing Node.js dependencies..."
    cd frontend
    npm install
    cd ..
else
    echo "[2/3] Node.js dependencies already installed. Skipping."
fi

# Copy .env if not exists
if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env
    echo "[3/3] Created backend/.env - please edit with your API keys."
else
    echo "[3/3] .env already exists."
fi

echo ""
echo "Starting services..."
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

cd backend
python run.py &
BACKEND_PID=$!
cd ..

sleep 2

cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

wait $BACKEND_PID $FRONTEND_PID
