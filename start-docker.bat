@echo off
REM PedalBot Docker Quick Start Script for Windows

echo 🚀 Starting PedalBot Background Services...
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not installed!
    echo 📥 Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/
    exit /b 1
)

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not running!
    echo 🔧 Please start Docker Desktop and try again.
    exit /b 1
)

echo ✅ Docker is ready
echo.

REM Build and start services
echo 🏗️  Building and starting services...
docker-compose up -d --build

REM Wait for services to be healthy
echo.
echo ⏳ Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Check service status
echo.
echo 📊 Service Status:
docker-compose ps

echo.
echo ✅ All services started!
echo.
echo 📍 Access Points:
echo    - Redis: localhost:6379
echo    - Flower Dashboard: http://localhost:5555
echo.
echo 📝 Useful Commands:
echo    - View logs: docker-compose logs -f
echo    - Stop services: docker-compose down
echo    - Restart worker: docker-compose restart celery-worker
echo.
echo 🧪 Test your setup:
echo    uv run python -m backend.test.test_mail
echo.

pause
