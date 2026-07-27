# Stage 1: 构建前端
FROM node:20-alpine AS frontend
WORKDIR /ui
COPY web-ui/package*.json ./
RUN npm install
COPY web-ui/ ./
RUN mkdir -p /probe/web/static && npm run build

# Stage 2: Python 运行时
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk maven graphviz && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/default-java
WORKDIR /app
COPY --from=frontend /probe/web/static ./probe/web/static
COPY pyproject.toml ./
COPY probe ./probe
COPY demo_mechanisms.py ./
COPY demo-repo ./demo-repo
ENV PROBE_DEMO_REPO=/app/demo-repo
RUN pip install --no-cache-dir -e ".[dev]"
EXPOSE 8000
CMD ["uvicorn", "probe.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
