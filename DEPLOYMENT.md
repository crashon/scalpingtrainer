# Deployment Guide

This guide covers running the Scalping Trainer API in production with safe CORS, a single engine process, and health checks.

## Environment

- **Python**: 3.10+
- **Ports**: 8001 (or behind a reverse proxy)
- **Environment variables**
  - `ALLOWED_ORIGINS`: Comma-separated origins allowed by CORS. Example:
    - `https://app.example.com,https://admin.example.com`
    - Default: `*` (development only)
  - `CORS_ALLOW_CREDENTIALS`: `true` or `false` (default `false`)
  - Optional: `REDIS_URL` if using Redis features.

## Start the server (single worker)

Run one process to ensure a single `AITradingEngine` instance per host:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --log-level info
```

Notes:
- The engine is per-process. To scale API horizontally, externalize the engine (see Scaling).

## Windows process manager options

### Task Scheduler
- Action: Start a program
- Program/script: `python`
- Arguments: `-m uvicorn main:app --host 0.0.0.0 --port 8001 --log-level info`
- Conditions: Run at startup, restart on failure.
- Configure environment variables (`ALLOWED_ORIGINS`, `CORS_ALLOW_CREDENTIALS`).

### NSSM (Non-Sucking Service Manager)
- `nssm install ScalpingTrainer "C:\\Path\\To\\python.exe" "-m uvicorn main:app --host 0.0.0.0 --port 8001 --log-level info"`
- Set stdout/stderr log files and rotation.

## Reverse proxy (optional)

- Terminate TLS at Nginx/IIS/Cloudflare and route to `http://localhost:8001`.
- Ensure WebSocket upgrade for `/ws/*` paths.
- Restrict external access to only required routes and origins.

### Nginx example
```nginx
server {
  listen 443 ssl;
  server_name api.example.com;

  ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

  location / {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
  }
}
```

## Health and readiness

- `GET /healthz` returns `{ "status": "ok" }`.
- `GET /readyz` returns readiness information (checks Redis if configured).
- Optional: `GET /metrics` exposes Prometheus metrics if `prometheus_client` is installed.

## E2E Test (local and CI)

- Local: `python tests/run_e2e_ci.py`
- GitHub Actions: `.github/workflows/e2e.yml` is provided to run on push/PR.

## Scaling

The current design assumes one `AITradingEngine` per process. To scale beyond one API worker:

- Run the engine as a separate process/service.
- Use Redis/pub-sub or a message queue for activity events and state.
- Have the FastAPI app subscribe to engine events and push to WebSocket clients.
- This allows multiple API workers for higher throughput while keeping a single engine.
