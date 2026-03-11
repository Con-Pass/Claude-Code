# Docker Deployment Guide

## 🐳 Quick Start

### Build the Image

```bash
docker build -t conpass-agent-backend:local .
```

### Run the Container

```bash
docker run -d \
  --name conpass-agent \
  --env-file .env \
  -p 8000:8000 \
  conpass-agent-backend:local
```

### Verify

```bash
# Check container status
docker ps | grep conpass-agent

# View logs
docker logs conpass-agent

# Test API
curl http://localhost:8000/health
```

---

## 📋 Available Commands

### Container Management

```bash
# Start container
docker start conpass-agent

# Stop container
docker stop conpass-agent

# Restart container
docker restart conpass-agent

# Remove container
docker rm -f conpass-agent

# View logs (follow)
docker logs conpass-agent -f

# View last 50 lines
docker logs conpass-agent --tail 50

# Execute command in container
docker exec -it conpass-agent /bin/sh
```

### Image Management

```bash
# List images
docker images | grep conpass-agent

# Remove image
docker rmi conpass-agent-backend:local

# Rebuild (no cache)
docker build --no-cache -t conpass-agent-backend:local .

# Tag image
docker tag conpass-agent-backend:local conpass-agent-backend:v1.0.0
```

---

## 🔧 Configuration

### Environment Variables

The container uses the `.env` file for configuration. Required variables:

```env
# Application
ENVIRONMENT=development
APP_HOST=0.0.0.0
APP_PORT=8000

# API Keys (Secrets)
OPENAI_API_KEY=your-google-ai-key
QDRANT_API_KEY=your-qdrant-key
QDRANT_URL=https://your-qdrant-url
QDRANT_COLLECTION=your-collection

# LLM Configuration
MODEL_PROVIDER=gemini
MODEL=gemini-2.5-flash
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_DIM=1024

# RAG Settings
TOP_K=5
CHUNK_SIZE=1024
CHUNK_OVERLAP=100
LLM_TEMPERATURE=0.3

# Prompts
SYSTEM_PROMPT=You are a helpful AI assistant...
FILESERVER_URL_PREFIX=http://localhost:8000
```

### Alternative: Pass Variables Individually

```bash
docker run -d \
  --name conpass-agent \
  -e ENVIRONMENT=production \
  -e OPENAI_API_KEY=your-key \
  -e QDRANT_URL=https://your-qdrant \
  -e QDRANT_API_KEY=your-qdrant-key \
  -e QDRANT_COLLECTION=docs \
  -e MODEL_PROVIDER=gemini \
  -e MODEL=gemini-2.5-flash \
  -e EMBEDDING_MODEL=text-embedding-004 \
  -e EMBEDDING_DIM=1024 \
  -e TOP_K=5 \
  -e CHUNK_SIZE=1024 \
  -e CHUNK_OVERLAP=100 \
  -e LLM_TEMPERATURE=0.3 \
  -e SYSTEM_PROMPT="You are a helpful AI assistant" \
  -e FILESERVER_URL_PREFIX=http://localhost:8000 \
  -p 8000:8000 \
  conpass-agent-backend:local
```

---

## 🌐 Endpoints

Once running, access these endpoints:

| Endpoint             | Description            | URL                                       |
| -------------------- | ---------------------- | ----------------------------------------- |
| Root                 | API information        | http://localhost:8000/                    |
| Health               | Health check           | http://localhost:8000/health              |
| Swagger UI           | Interactive API docs   | http://localhost:8000/docs                |
| ReDoc                | Alternative docs       | http://localhost:8000/redoc               |
| OpenAPI Schema       | JSON schema            | http://localhost:8000/openapi.json        |
| Chat (Streaming)     | POST streaming chat    | http://localhost:8000/api/v1/chat         |
| Chat (Non-streaming) | POST complete response | http://localhost:8000/api/v1/chat/request |
| Chat Config          | GET configuration      | http://localhost:8000/api/v1/chat/config  |

---

## 🔍 Troubleshooting

### Container Won't Start

```bash
# Check logs for errors
docker logs conpass-agent

# Check if port is already in use
lsof -i :8000
# or
netstat -an | grep 8000

# Run in foreground to see errors
docker run --rm --env-file .env -p 8000:8000 conpass-agent-backend:local
```

### API Key Errors

If you see "API key not valid" errors:

```bash
# Verify environment variables are loaded
docker exec conpass-agent env | grep -E "OPENAI|QDRANT"

# Check the .env file
cat .env | grep -E "OPENAI|QDRANT"

# Restart with updated .env
docker restart conpass-agent
```

### High Memory Usage

```bash
# Check container resource usage
docker stats conpass-agent

# Limit memory usage
docker run -d \
  --name conpass-agent \
  --env-file .env \
  --memory="2g" \
  --cpus="1.0" \
  -p 8000:8000 \
  conpass-agent-backend:local
```

---

## 🚀 Production Deployment

### Using Docker Compose

Create `docker-compose.yml`:

```yaml
version: "3.8"

services:
  conpass-agent:
    build: .
    image: conpass-agent-backend:latest
    container_name: conpass-agent
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - ENVIRONMENT=production
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 4G
        reservations:
          cpus: "1"
          memory: 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

Run with Docker Compose:

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker-compose logs -f

# Restart
docker-compose restart
```

### Multi-Stage Build (Optimized)

The Dockerfile is already using multi-stage build for optimization:

```dockerfile
# Stage 1: Install dependencies
FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Stage 2: Copy application
COPY . .

# Run
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Push to Registry

```bash
# Tag for registry
docker tag conpass-agent-backend:local gcr.io/PROJECT_ID/conpass-agent:v1.0.0

# Push to Google Container Registry
docker push gcr.io/PROJECT_ID/conpass-agent:v1.0.0

# Or push to Docker Hub
docker tag conpass-agent-backend:local username/conpass-agent:v1.0.0
docker push username/conpass-agent:v1.0.0
```

---

## 📊 Monitoring

### View Real-time Logs

```bash
# All logs
docker logs conpass-agent -f

# Last 100 lines
docker logs conpass-agent --tail 100 -f

# With timestamps
docker logs conpass-agent -f --timestamps
```

### Health Monitoring

```bash
# Simple health check script
#!/bin/bash
while true; do
  response=$(curl -s http://localhost:8000/health)
  if echo "$response" | grep -q "healthy"; then
    echo "$(date): ✅ Service is healthy"
  else
    echo "$(date): ❌ Service is down"
  fi
  sleep 30
done
```

---

## 🔄 Updates and Maintenance

### Update Application

```bash
# 1. Stop and remove old container
docker stop conpass-agent
docker rm conpass-agent

# 2. Pull latest code
git pull origin main

# 3. Rebuild image
docker build -t conpass-agent-backend:latest .

# 4. Run new container
docker run -d \
  --name conpass-agent \
  --env-file .env \
  -p 8000:8000 \
  conpass-agent-backend:latest
```

### Backup and Restore

```bash
# Export image
docker save conpass-agent-backend:local > conpass-agent-backup.tar

# Import image
docker load < conpass-agent-backup.tar
```

---

## 🛡️ Security Best Practices

1. **Don't expose sensitive data**

   - Use `.env` files (never commit to git)
   - Use Docker secrets in production
   - Rotate API keys regularly

2. **Run as non-root user**

   ```dockerfile
   USER nobody:nobody
   ```

3. **Scan for vulnerabilities**

   ```bash
   docker scan conpass-agent-backend:local
   ```

4. **Use specific versions**
   ```dockerfile
   FROM python:3.12.12-slim
   ```

---

## 📖 Additional Resources

- [Dockerfile Reference](./Dockerfile)
- [API Documentation](./API_DOCUMENTATION.md)
- [Deployment Guide](./.github/workflows/SETUP_GUIDE.md)
- [Main README](./README.md)

---

## 🆘 Support

For issues:

1. Check container logs: `docker logs conpass-agent`
2. Verify environment variables: `docker exec conpass-agent env`
3. Test health endpoint: `curl http://localhost:8000/health`
4. Review API docs: http://localhost:8000/docs
