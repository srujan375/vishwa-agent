#!/bin/bash
# Quick setup script for Vishwa on Mac/Linux

set -e

echo "============================================================"
echo "Vishwa Quick Setup"
echo "============================================================"
echo ""

# Check Python version
echo "[1/5] Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found. Please install Python 3.10+"
    echo "Download from: https://www.python.org/downloads/"
    exit 1
fi

python3 --version
echo ""

# Create virtual environment
echo "[2/5] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created venv"
else
    echo "venv already exists"
fi
echo ""

# Activate virtual environment
echo "[3/5] Activating virtual environment..."
source venv/bin/activate
echo ""

# Install dependencies
echo "[4/5] Installing Vishwa and dependencies..."
pip install -e . --quiet
echo "Installed successfully"
echo ""

# Check configuration
echo "[5/5] Checking configuration..."
if [ ! -f ".env" ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "[!] Please edit .env and add your API keys"
    echo "    ANTHROPIC_API_KEY=sk-ant-..."
    echo "    or"
    echo "    OPENAI_API_KEY=sk-..."
    echo ""
else
    echo ".env file exists"
fi

echo ""
echo "============================================================"
echo "Setup Complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env file and add your API key"
echo "  2. Run: vishwa check"
echo "  3. Try: vishwa \"list all Python files\""
echo ""
echo "To activate virtual environment later:"
echo "  source venv/bin/activate"
echo ""
