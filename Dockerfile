# One image: FastAPI serves the API under /api and the built frontend at /.
# Configuration comes from environment variables (see .env.example); no .env file goes into the image.
# Base images are the Docker Official Images from the AWS ECR Public mirror: no Docker Hub pull limits.

FROM public.ecr.aws/docker/library/node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM public.ecr.aws/docker/library/python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 1000 app \
    && mkdir /data && chown app:app /data
COPY core/ core/
COPY agents/ agents/
COPY prompts/ prompts/
COPY server/ server/
COPY --from=frontend /app/frontend/dist/ frontend/dist/

# SQLite lives on a persistent volume mounted at /data.
ENV SDR_DB_PATH=/data/sdr.sqlite3 \
    SDR_STATIC_DIR=/app/frontend/dist \
    PORT=8000
VOLUME /data
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=4)"

# One worker only: runs, cancellation and SSE wake-ups live in this process's memory.
# Proxy headers are read from the addresses in FORWARDED_ALLOW_IPS (uvicorn's default: 127.0.0.1);
# behind a hosting proxy set it to the proxy's address, or the per-visitor quota sees one client.
# On stop, open SSE streams get 10 s, then active runs are cancelled before their next paid call.
CMD ["sh", "-c", "exec uvicorn server.app:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers --timeout-graceful-shutdown 10"]
