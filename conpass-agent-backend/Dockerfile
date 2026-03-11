FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-jpn \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    build-essential \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml ./

# CPU-only torch を先にインストールしてイメージサイズを削減
# FlagEmbedding はデフォルトで CUDA 版 torch を引き込むため、先に CPU 版を固定する
RUN uv venv && uv pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies (FlagEmbedding を含む)
RUN uv sync --no-dev

# Copy application code
COPY . .

EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port 8080"]