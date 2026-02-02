# =============================================================================
# DJANGO PRODUCTION DOCKERFILE
# JanMitra Backend - Government Intelligence Reporting System
# =============================================================================

FROM python:3.11-slim-bookworm AS base

# Prevent Python from writing bytecode and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd --gid 1000 janmitra && \
    useradd --uid 1000 --gid janmitra --shell /bin/bash --create-home janmitra

WORKDIR /app

# =============================================================================
# BUILDER STAGE - Install dependencies
# =============================================================================
FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# =============================================================================
# PRODUCTION STAGE
# =============================================================================
FROM base AS production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create necessary directories
RUN mkdir -p /app/staticfiles /app/encrypted_media /app/logs && \
    chown -R janmitra:janmitra /app

# Copy application code
COPY --chown=janmitra:janmitra . .

# Copy gunicorn config
COPY --chown=janmitra:janmitra gunicorn.conf.py /app/

# Switch to non-root user
USER janmitra

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Default command - run with gunicorn
CMD ["gunicorn", "--config", "gunicorn.conf.py", "janmitra_backend.wsgi:application"]
