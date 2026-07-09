FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jdk maven graphviz && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/default-java
WORKDIR /app
COPY pyproject.toml ./
COPY probe ./probe
COPY demo_mechanisms.py ./
RUN pip install --no-cache-dir -e ".[dev]"
EXPOSE 8000
CMD ["uvicorn", "probe.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
