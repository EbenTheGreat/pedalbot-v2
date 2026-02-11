#!/bin/bash

# PedalBot Docker Quick Start Script

echo "🚀 Starting PedalBot Background Services..."
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo "📥 Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running!"
    echo "🔧 Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is ready"
echo ""

# Build and start services
echo "🏗️  Building and starting services..."
docker-compose up -d --build

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service status
echo ""
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "✅ All services started!"
echo ""
echo "📍 Access Points:"
echo "   - Redis: localhost:6379"
echo "   - Flower Dashboard: http://localhost:5555"
echo ""
echo "📝 Useful Commands:"
echo "   - View logs: docker-compose logs -f"
echo "   - Stop services: docker-compose down"
echo "   - Restart worker: docker-compose restart celery-worker"
echo ""
echo "🧪 Test your setup:"
echo "   uv run python -m backend.test.test_mail"
echo ""
