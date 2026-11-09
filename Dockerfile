FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp (manual-link-audio-capture, filmot path) needs a JS runtime to solve
# YouTube's player challenges — recent yt-dlp defaults to deno and warns
# ("No supported JavaScript runtime could be found") without one, which in
# practice correlates with YouTube's "Sign in to confirm you're not a bot"
# extraction failures. Installed via deno's own install script (no apt
# package) into a fixed path already on PATH for the app user below.
ENV DENO_INSTALL=/usr/local
RUN curl -fsSL https://deno.land/install.sh | sh

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app.py auth.py blob_storage.py smia_client.py settings_store.py similarity.py .
COPY db/ ./db/
COPY routes/ ./routes/
COPY ui/ ./ui/
COPY alembic.ini .
COPY alembic/ ./alembic/
COPY scripts/ ./scripts/

EXPOSE 5056

CMD ["python", "-m", "scripts.bootstrap"]
