#!/bin/bash

# OFSAA Installation - PM2 Quick Start Script
# Usage: bash start-pm2.sh

echo "======================================"
echo "OFSAA Installation - PM2 Setup"
echo "======================================"
echo ""

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "ERROR: PM2 is not installed"
    echo "Install it with: npm install -g pm2"
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed (Python package manager)"
    echo "Install it with: pip install uv or curl https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if Node.js/Bun is installed
if ! command -v bun &> /dev/null; then
    echo "WARNING: bun is not installed"
    echo "Install it with: npm install -g bun"
    echo "Or use node: npm install -g n && n latest"
    exit 1
fi

echo "✓ All prerequisites found"
echo ""

# Step 1: Setup Frontend
echo "Step 1: Installing frontend dependencies..."
cd frontend
bun install || npm install
if [ ! -f ".env.local" ]; then
    echo "Creating .env.local with API URL..."
    echo "NEXT_PUBLIC_API_URL=http://192.168.0.165:8000" > .env.local
fi
cd ..
echo "✓ Frontend setup complete"
echo ""

# Step 2: Build Frontend
echo "Step 2: Building frontend for production..."
cd frontend
bun run build || npm run build
cd ..
echo "✓ Frontend build complete"
echo ""

# Step 3: Setup Backend
echo "Step 3: Installing backend dependencies..."
cd backend
uv sync
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "⚠ Please edit backend/.env with your Git and database credentials"
fi
cd ..
echo "✓ Backend setup complete"
echo ""

# Step 4: Check ecosystem.config.js
if [ ! -f "ecosystem.config.js" ]; then
    echo "ERROR: ecosystem.config.js not found in project root"
    exit 1
fi
echo "✓ PM2 configuration file found"
echo ""

# Step 5: Start with PM2
echo "Step 5: Starting services with PM2..."
pm2 delete all 2>/dev/null || true
pm2 start ecosystem.config.js
echo "✓ Services started"
echo ""

# Step 6: Save PM2 config for auto-start
echo "Step 6: Saving PM2 configuration..."
pm2 startup
pm2 save
echo "✓ PM2 auto-start configured"
echo ""

echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Access the application at:"
echo "  Frontend: http://192.168.0.165:3000"
echo "  Backend:  http://192.168.0.165:8000"
echo ""
echo "View logs:"
echo "  pm2 logs"
echo "  pm2 logs frontend"
echo "  pm2 logs backend"
echo ""
echo "Monitor services:"
echo "  pm2 monit"
echo ""
