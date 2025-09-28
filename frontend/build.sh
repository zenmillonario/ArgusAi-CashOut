#!/bin/bash

# Render Build Script for ArgusAI Frontend
echo "🔧 Starting ArgusAI Frontend Build..."

# Install dependencies (ignore frozen lockfile for Render)
echo "📦 Installing dependencies..."
yarn install --frozen-lockfile=false

# Build the React application
echo "🏗️ Building React application..."
yarn build

# Verify build completed successfully
if [ -d "build" ]; then
    echo "✅ Frontend build completed successfully!"
    echo "📁 Build directory created with $(ls -la build | wc -l) files"
else
    echo "❌ Build failed - no build directory created"
    exit 1
fi