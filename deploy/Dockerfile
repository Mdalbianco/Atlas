# Immagine base sostituibile (es. mirror.gcr.io/library/python:3.12-slim se Docker Hub limita i download)
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN useradd --create-home --uid 10001 atlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY atlas ./atlas
COPY main.py pyproject.toml ./
RUN mkdir -p /app/data && chown -R atlas:atlas /app
USER atlas

VOLUME ["/app/data"]
HEALTHCHECK --interval=5m --timeout=20s --start-period=10m --retries=3 CMD ["python", "-m", "atlas", "healthcheck"]
CMD ["python", "-m", "atlas", "run"]
