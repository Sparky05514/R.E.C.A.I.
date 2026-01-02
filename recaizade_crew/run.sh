#!/bin/bash

# Source the virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the UI application
python3 ui.py
