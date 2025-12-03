#!/bin/bash

# Chiliz Marketing Intelligence v3.0 - Railway Deployment Script

echo "======================================"
echo "Chiliz Marketing Intelligence v3.0"
echo "Railway Deployment"
echo "======================================"

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Railway CLI not found. Installing..."
    npm install -g @railway/cli
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "Please login to Railway first:"
    railway login
fi

echo ""
echo "Creating new Railway project..."
railway init

echo ""
echo "Adding TimescaleDB..."
echo "Note: You'll need to add TimescaleDB manually from the Railway dashboard"
echo "Go to: https://railway.app -> Your Project -> Add New Service -> Database -> TimescaleDB"

echo ""
echo "Please set the following environment variables in Railway dashboard:"
echo "  - COINGECKO_API_KEY"
echo "  - X_BEARER_TOKEN"
echo "  - OPENROUTER_API_KEY"
echo "  - SLACK_WEBHOOK_URL"
echo "  - TIMESCALE_HOST (from TimescaleDB service)"
echo "  - TIMESCALE_PORT"
echo "  - TIMESCALE_DB"
echo "  - TIMESCALE_USER"
echo "  - TIMESCALE_PASSWORD"

echo ""
echo "Deploying to Railway..."
railway up --detach

echo ""
echo "Deployment initiated!"
echo ""
echo "Next steps:"
echo "1. Add TimescaleDB from Railway dashboard"
echo "2. Set all environment variables"
echo "3. Run the database migration"
echo "4. Monitor logs with: railway logs"
echo ""
echo "Dashboard URL will be available after deployment completes."
