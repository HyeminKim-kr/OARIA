#!/bin/bash

# OARIA 3D Vector Graph Server - PM2 Production
# Port: 10000

cd "$(dirname "$0")"

APP_NAME="oaria-3d-graph"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Always build for production
echo "Building production version..."
npm run build

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "PM2 not found. Installing globally..."
    npm install -g pm2
fi

# Stop existing instance if running
pm2 stop $APP_NAME 2>/dev/null
pm2 delete $APP_NAME 2>/dev/null

# Start with PM2
echo "Starting 3D Graph Server with PM2 on port 10000..."
pm2 start npm --name $APP_NAME -- run start

# Save PM2 process list
pm2 save

echo ""
echo "================================"
echo "3D Graph Server started with PM2"
echo "App name: $APP_NAME"
echo "Port: 10000"
echo ""
echo "Useful commands:"
echo "  pm2 logs $APP_NAME    - View logs"
echo "  pm2 status            - Check status"
echo "  pm2 restart $APP_NAME - Restart"
echo "  pm2 stop $APP_NAME    - Stop"
echo "================================"
