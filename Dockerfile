# kidtube server (ADR 0023). One process: admin page, TV API, streaming, download worker.
FROM python:3.12-slim

# ffmpeg merges and converts downloads; deno lets yt-dlp solve YouTube's player challenges.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/*
COPY --from=denoland/deno:bin-2.5.6 /deno /usr/local/bin/deno

WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/app ./app
COPY server/migrations ./migrations

ENV KIDTUBE_DATA_DIR=/data \
    KIDTUBE_LIBRARY_DIR=/library \
    PYTHONUNBUFFERED=1 \
    DENO_DIR=/data/.deno \
    HOME=/data
EXPOSE 8460
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8460/healthz').status==200 else 1)"
CMD ["uvicorn", "app.main:app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8460"]
