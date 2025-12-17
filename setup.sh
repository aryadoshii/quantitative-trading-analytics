#!/bin/bash

# Setup script for Quantitative Trading Analytics Application

echo "================================================"
echo "  Quantitative Trading Analytics Setup"
echo "================================================"
echo ""

# Check if Python 3.9+ is installed
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Found Python $python_version"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi
echo "✓ Docker is installed"

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed. Please install docker-compose first."
    exit 1
fi
echo "✓ docker-compose is installed"

echo ""
echo "Step 1: Starting Docker services (TimescaleDB + Redis)..."
docker-compose up -d

# Wait for databases to be ready
echo "Waiting for databases to initialize..."
sleep 10

echo ""
echo "Step 2: Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "Step 3: Creating logs directory..."
mkdir -p logs

echo ""
echo "================================================"
echo "  Setup Complete! ✅"
echo "================================================"
echo ""
echo "To start the application:"
echo ""
echo "  Terminal 1 (Backend + Data Ingestion):"
echo "    python src/main.py"
echo ""
echo "  Terminal 2 (Frontend Dashboard):"
echo "    streamlit run src/app.py"
echo ""
echo "The dashboard will be available at:"
echo "  http://localhost:8501"
echo ""
echo "To stop Docker services:"
echo "  docker-compose down"
echo ""
