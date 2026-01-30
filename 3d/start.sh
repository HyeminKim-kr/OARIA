#!/bin/bash

# OARIA 3D Vector Graph Server
# Port: 10000

cd "$(dirname "$0")"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Development mode
if [ "$1" = "dev" ]; then
    echo "Starting 3D Graph Server in development mode on port 10000..."
    npm run dev
else
    # Production mode
    if [ ! -d ".next" ]; then
        echo "Building production version..."
        npm run build
    fi
    echo "Starting 3D Graph Server in production mode on port 10000..."
    npm run start
fi
