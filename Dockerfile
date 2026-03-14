# ARG declared before any FROM so it can be used in FROM instructions
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20

# ════════════════════════════════════════════════════════════
#  Stage 1 – Build the React frontend
# ════════════════════════════════════════════════════════════
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Install dependencies first (layer cache)
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --prefer-offline

# Build production bundle
COPY ui/ .
RUN npm run build


# ════════════════════════════════════════════════════════════
#  Stage 2 – Production image (Home Assistant base)
# ════════════════════════════════════════════════════════════
FROM ${BUILD_FROM}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System deps needed by pdfplumber / Pillow
RUN apk add --no-cache \
    bash \
    jpeg-dev \
    freetype-dev \
    zlib-dev \
    libffi-dev \
    build-base \
    python3-dev

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Application source
COPY app/        ./app/
COPY migrations/ ./migrations/
COPY alembic.ini .

# Built frontend assets (served by FastAPI in production)
COPY --from=frontend-builder /build/dist ./ui/dist/

# Startup script
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
