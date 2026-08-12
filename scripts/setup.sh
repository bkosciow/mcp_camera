#!/bin/bash
set -e

echo "📸 Camera MCP — Setup Script"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose v2+."
    exit 1
fi

# Copy environment file
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your configuration"
else
    echo "✅ .env file already exists"
fi

# Start development services
echo "🐳 Starting development services..."
docker compose up -d --build

echo ""
echo "✅ Setup complete!"
echo ""
echo "📌 Next steps:"
echo "   1. Edit .env with your configuration"
echo "   2. Uncomment the devices line in docker compose.yml for camera passthrough"
echo "   3. Open http://localhost:8579/health to verify"
echo ""
echo "📚 Useful commands:"
echo "   make dev        - Start development"
echo "   make test       - Run tests"
echo "   make prod-up    - Start production"
echo "   make help       - Show all commands"
