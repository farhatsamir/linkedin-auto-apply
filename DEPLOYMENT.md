# Deployment Guide — LinkedIn Auto Apply SaaS

This guide walks through deploying this system to a real external server,
building on the Docker setup completed in Phase 5.

## Prerequisites on the target server

- Docker and Docker Compose installed
- A domain name pointed at the server (for production use)
- At minimum: 4 CPU cores, 8GB RAM (Ollama with gemma3:4b needs real resources)

## Files needed on the server

Copy these from your project to the server:
- All application code (`app/`, `alembic/`)
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `.dockerignore`

Do NOT copy `.env`, `.env.docker`, or `.env.compose` — these contain
secrets and must be created fresh on the server (see below).

## Setting up secrets on the server

1. Copy `.env.production.example` to `.env.docker` on the server
2. Fill in every `REPLACE_WITH_...` placeholder with real, strong values
   - Generate secrets with: `python3 -c "import secrets; print(secrets.token_hex(32))"`
3. Create `.env.compose` on the server with just:


DB_PASSWORD=<same password used in DATABASE_URL above>
REDIS_PASSWORD=<same password used in REDIS_URL above>


## Starting the stack

```bash
docker-compose --env-file .env.compose up -d --build
```

Verify all containers are healthy:
```bash
docker-compose --env-file .env.compose ps
curl http://localhost:8001/health
```

## Ollama on production

[This section will be filled in after the dedicated Ollama production
discussion — see project notes.]

## Updating a live deployment

1. Pull/copy the new code to the server
2. Rebuild and restart only the changed services:
```bash
   docker-compose --env-file .env.compose up -d --build api worker
```
3. Alembic migrations run automatically on `api` container startup

## Rolling back

Docker keeps the previous image until a new one is built. To roll back:
```bash
docker-compose --env-file .env.compose down
docker tag <previous-image-id> linkedin_auto_apply-api:latest
docker-compose --env-file .env.compose up -d
```

## Monitoring

- Health check: `GET /health`
- Admin log view: `GET /logs/admin/all` (requires admin token)
- Admin run view: `GET /auto-apply/admin/runs` (requires admin token)