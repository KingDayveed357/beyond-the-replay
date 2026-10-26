# One container: FastAPI serves the API, live streams and ingestion feeds, the A2A endpoint and the built frontend.
# Targets: Azure Container Apps (preferred), or any container host. Listens on $PORT (default 8000).
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 BTR_RUNTIME=/tmp/btr-runtime
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY phase0/ phase0/
COPY investigation/ investigation/
COPY analytics/ analytics/
COPY server/ server/
COPY mcp_server/ mcp_server/
COPY schemas/ schemas/
COPY data/ data/
COPY results/*.json results/
COPY --from=web /web/dist web/dist
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
# --proxy-headers: behind Azure ingress, use the visitor address from X-Forwarded-For (per-visitor rate limits).
CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips '*' --timeout-keep-alive 75"]
