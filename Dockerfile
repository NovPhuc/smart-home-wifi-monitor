# Dockerfile cho An Tâm Home — bản 2310
# Build:   docker build -t an-tam-home:2310 .
# Chạy:    docker run -d -p 5000:5000 -v $(pwd)/data:/app/data -v $(pwd)/models:/app/models --name an-tam-home an-tam-home:2310
# Hoặc:    docker compose up -d
# Dev:     docker build --target dev -t an-tam-home:dev .
# Archive: docker build --target archive -t an-tam-home:archive . && docker run --rm -v ${PWD}/output:/out an-tam-home:archive

# =============================================================================
# Stage 1: Base Python với dependencies dev (CUDA PyTorch)
# =============================================================================
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements trước để tận dụng cache layer
COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# =============================================================================
# Stage 2: Development image (có toàn bộ source, không chạy server)
# =============================================================================
FROM base AS dev

# Cài tools dev
RUN pip install pytest black ruff mypy

# Copy toàn bộ source code
COPY . .

# Tạo thư mục data/models nếu chưa có
RUN mkdir -p /app/data /app/models

EXPOSE 5000

# Default command cho dev: chạy test
CMD ["pytest", "tests", "-v"]

# =============================================================================
# Stage 3: Production image (CPU-only PyTorch, non-root user)
# =============================================================================
FROM python:3.11-slim AS prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH=/app/src

# Tạo user non-root.
#
# `useradd -r` (system account) KHÔNG tạo thư mục home. Gunicorn 26 mở một
# "control server" và ghi socket vào $HOME/.gunicorn — không có home thì mỗi lần
# khởi động in `[ERROR] Control server error: [Errno 13] Permission denied`.
# Lỗi này không làm sập server nhưng làm nhiễu log và che mất lỗi thật.
# Tạo home riêng thay vì trỏ HOME vào /app/data để socket không nằm lẫn trong
# volume dữ liệu (dễ nhầm khi sao lưu).
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && mkdir -p /home/appuser && chown -R appuser:appuser /home/appuser
ENV HOME=/home/appuser

# Copy requirements CPU-only
COPY requirements-docker.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements-docker.txt

# Copy source code cần thiết
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser server/ ./server/
COPY --chown=appuser:appuser config.yaml ./
COPY --chown=appuser:appuser .env.example ./

# Tạo thư mục data/models và set quyền
RUN mkdir -p /app/data /app/models && \
    chown -R appuser:appuser /app/data /app/models

USER appuser

EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

# Chạy server.
#
# KHÔNG dùng `python server/app.py` ở đây: đó là Werkzeug dev server (một tiến
# trình, in cảnh báo đỏ, không có worker pool). Gunicorn với worker `gthread` là
# bắt buộc vì dashboard dùng Server-Sent Events ở /api/stream — worker `sync`
# sẽ giữ trọn một tiến trình cho mỗi kết nối SSE.
#   2 worker × 8 luồng = 16 request đồng thời, trần SSE của app là 32 kết nối.
#   --timeout 300 để SSE (heartbeat 15 giây) không bị cắt giữa chừng.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--worker-class", "gthread", "--workers", "2", "--threads", "8", \
     "--timeout", "300", "--graceful-timeout", "30", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "server.wsgi:application"]

# =============================================================================
# Stage 4: Full source image (để chia sẻ/backup toàn bộ project)
# =============================================================================
FROM alpine:3.20 AS full-source

RUN apk add --no-cache tar gzip

WORKDIR /src

# Copy toàn bộ project (trừ cache/build)
COPY . .

# Dọn rác
RUN rm -rf \
    android_collector/.gradle \
    android_collector/app/build \
    android_collector/build \
    android_collector/local.properties \
    android_collector/.idea \
    android_collector/.kotlin \
    server/__pycache__ \
    server/routes/__pycache__ \
    src/smarthome/__pycache__ \
    src/smarthome/models/__pycache__ \
    tests/__pycache__ \
    scripts/__pycache__ \
    .pytest_cache \
    .venv \
    .vscode \
    .github \
    .tmp \
    .trace-mcp \
    .playwright-cli \
    backup_original \
    runlogs \
    notebooks \
    *.log \
    train_*.bat

# Tạo archive tar.gz
RUN tar -czf /project.tar.gz .

# Final scratch image chỉ chứa archive
FROM scratch AS archive
COPY --from=full-source /project.tar.gz /an-tam-home-2310-full-source.tar.gz