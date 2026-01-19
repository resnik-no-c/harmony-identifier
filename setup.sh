#!/bin/bash

# Harmony Identifier Setup Script
# This script sets up all dependencies for the app

set -e  # Exit on any error

echo ""
echo "======================================"
echo "  Harmony Identifier Setup"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
status() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

# Check for required tools
echo "Checking requirements..."
echo ""

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    status "Node.js installed: $NODE_VERSION"
else
    error "Node.js not found!"
    echo "  Please install it with: brew install node"
    exit 1
fi

# Check npm
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    status "npm installed: v$NPM_VERSION"
else
    error "npm not found!"
    echo "  Please install Node.js with: brew install node"
    exit 1
fi

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    status "Python installed: $PYTHON_VERSION"
else
    error "Python 3 not found!"
    echo "  Please install it with: brew install python@3.11"
    exit 1
fi

# Check FFmpeg
if command -v ffmpeg &> /dev/null; then
    status "FFmpeg installed"
else
    warning "FFmpeg not found - video file support will be limited"
    echo "  Install with: brew install ffmpeg"
fi

echo ""
echo "Installing JavaScript dependencies..."
echo ""

npm install

status "JavaScript dependencies installed"

echo ""
echo "Setting up Python environment..."
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "python/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv python/venv
    status "Virtual environment created"
else
    status "Virtual environment already exists"
fi

# Activate virtual environment
source python/venv/bin/activate

echo "Installing Python packages (this may take a few minutes)..."
echo ""

# Upgrade pip first
pip install --upgrade pip --quiet

# Install requirements
pip install -r python/requirements.txt

status "Python dependencies installed"

# Deactivate virtual environment
deactivate

echo ""
echo "======================================"
echo -e "  ${GREEN}Setup Complete!${NC}"
echo "======================================"
echo ""
echo "To run the app:"
echo ""
echo "  npm start"
echo ""
echo "Enjoy identifying harmonies! 🎵"
echo ""
