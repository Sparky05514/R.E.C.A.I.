#!/bin/bash

# Recaizade Crew Setup Script
# This script automates the environment setup for the Recaizade Crew project.

set -e

echo "🚀 Starting setup for Recaizade Crew..."

# 1. Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed. Please install it and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Found Python $PYTHON_VERSION"

# 2. Virtual Environment Setup
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists."
fi

# 3. Install Dependencies
echo "📥 Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Environment Variables Setup
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    echo "GOOGLE_API_KEY=your_api_key_here" > .env
    echo "⚠️  Created .env. Please update it with your GOOGLE_API_KEY."
else
    echo "✅ .env file already exists."
fi

echo "-----------------------------------------------"
echo "🎉 Setup complete!"
echo "To start the application, run:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo "-----------------------------------------------"
