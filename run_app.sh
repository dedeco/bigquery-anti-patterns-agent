#!/bin/bash

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file"
    export $(grep -v '^#' .env | xargs)
fi

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Warning: ANTHROPIC_API_KEY is not set. The application will fall back to rule-based analysis."
    echo "To use LLM features, set the ANTHROPIC_API_KEY environment variable or create a .env file."
fi

# Run the web interface with MCP tools
python app.py
