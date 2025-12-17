#!/bin/bash

# Run script for Quantitative Trading Analytics Application

echo "================================================"
echo "  Starting Quantitative Trading Analytics"
echo "================================================"
echo ""

# Check if Docker services are running
if ! docker ps | grep -q quantdev; then
    echo "⚠️  Docker services not running. Starting..."
    docker-compose up -d
    echo "Waiting for databases to initialize..."
    sleep 10
fi

echo "✓ Docker services running"
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

echo "Starting application components..."
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down application..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM

# Start backend in background
echo "Starting backend (data ingestion & analytics)..."
python src/main.py > logs/backend.log 2>&1 &
BACKEND_PID=$!

# Wait a bit for backend to initialize
sleep 5

# Start frontend
echo "Starting frontend dashboard..."
echo ""
echo "================================================"
echo "  Dashboard will open at:"
echo "  http://localhost:8501"
echo "================================================"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

streamlit run src/app.py &
FRONTEND_PID=$!

# Wait for either process to exit
wait
