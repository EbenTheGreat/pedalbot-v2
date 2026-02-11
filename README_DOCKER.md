# Docker Setup for PedalBot Background Jobs

This guide will help you set up and run Redis and Celery workers using Docker.

## Prerequisites

1. **Install Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop/
   - Run the installer and follow the setup wizard
   - Restart your computer if prompted
   - Verify installation:
     ```bash
     docker --version
     docker-compose --version
     ```  

## Quick Start

### 1. Start All Services
```bash
docker-compose up -d
```

This will start:
- **Redis** (port 6379) - Message broker
- **Celery Worker** - Processes background tasks
- **Celery Beat** - Runs scheduled tasks
- **Flower** (port 5555) - Monitoring dashboard

### 2. Check Service Status
```bash
docker-compose ps
```

### 3. View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat
docker-compose logs -f redis
```

### 4. Stop All Services
```bash
docker-compose down
```

### 5. Stop and Remove All Data
```bash
docker-compose down -v
```

## Monitoring

### Flower Dashboard
Once running, open your browser and go to:
```
http://localhost:5555
```

This provides:
- Active tasks
- Task history
- Worker status
- Task statistics
- Real-time monitoring

## Testing Email Tasks

### With Docker Running

Now you can run your email tests:

```bash
# Test with Celery (async)
uv run python -m backend.test.test_mail

# Test without Celery (sync)
uv run python -m backend.test.test_mail_sync
```

## Common Commands

### Restart a Service
```bash
docker-compose restart celery-worker
```

### Rebuild After Code Changes
```bash
docker-compose up -d --build
```

### Scale Workers
```bash
docker-compose up -d --scale celery-worker=3
```

### Access Redis CLI
```bash
docker-compose exec redis redis-cli
```

### Access Worker Shell
```bash
docker-compose exec celery-worker bash
```

## Troubleshooting

### Port Already in Use
If port 6379 is already in use:
```bash
# Find what's using the port
netstat -ano | findstr :6379

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### Worker Not Processing Tasks
1. Check worker logs:
   ```bash
   docker-compose logs -f celery-worker
   ```

2. Restart the worker:
   ```bash
   docker-compose restart celery-worker
   ```

### Redis Connection Issues
1. Check Redis is running:
   ```bash
   docker-compose ps redis
   ```

2. Test Redis connection:
   ```bash
   docker-compose exec redis redis-cli ping
   # Should return: PONG
   ```

### Clear All Tasks
```bash
docker-compose exec redis redis-cli FLUSHALL
```

## Development Workflow

### 1. Start Services
```bash
docker-compose up -d
```

### 2. Develop Your Code
Make changes to your Python files. The workers will automatically reload if you have volume mounts configured.

### 3. Test Tasks
```bash
uv run python -m backend.test.test_mail
```

### 4. Monitor in Flower
Open http://localhost:5555 to see task execution in real-time.

### 5. Stop Services When Done
```bash
docker-compose down
```

## Production Considerations

For production deployment:

1. **Use environment-specific configs**:
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

2. **Set resource limits** in docker-compose.yml:
   ```yaml
   celery-worker:
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 2G
   ```

3. **Use Docker secrets** for sensitive data instead of .env files

4. **Enable Redis persistence** (already configured with `appendonly yes`)

5. **Set up log aggregation** (e.g., ELK stack, CloudWatch)

## Architecture

```
┌─────────────────┐
│   Your App      │
│  (FastAPI/etc)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│     Redis       │◄────┤Celery Worker │
│  (Message Broker)│     │  (Tasks)     │
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│  Celery Beat    │     │   Flower     │
│  (Scheduler)    │     │ (Monitoring) │
└─────────────────┘     └──────────────┘
```

## Next Steps

1. ✅ Start Docker services: `docker-compose up -d`
2. ✅ Open Flower dashboard: http://localhost:5555
3. ✅ Run your email test: `uv run python -m backend.test.test_mail`
4. ✅ Check Flower to see the task execute
5. ✅ Check your email inbox for the welcome email

## Support

 For issues:
- Check logs: `docker-compose logs -f`
- Restart services: `docker-compose restart`
- Rebuild: `docker-compose up -d --build`
