FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl/ca-certificates come from the trusted base distro; no version pin needed.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 3005

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD curl -fsS http://localhost:3005/health || exit 1

# Threaded workers so a slow streaming LLM response doesn't block other requests.
CMD ["gunicorn", "--bind", "0.0.0.0:3005", "--workers", "1", "--threads", "8", \
     "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "app.main:app"]
