#!/bin/bash
# Setup script to install dependencies and pull Ollama models

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    echo "Error: Ollama is not installed. Please install Ollama first."
    exit 1
fi

echo "Pulling required Ollama models..."
# llama3.2 for general chat/reasoning (Recaizade, Reviewer, Executor)
echo "Pulling llama3.2..."
ollama pull llama3.2

# qwen2.5-coder for coding tasks (Coder)
echo "Pulling qwen2.5-coder..."
ollama pull qwen2.5-coder

echo "Setup complete. Models are ready."
