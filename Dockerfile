FROM python:3.11-slim

# Install system dependencies including Tesseract OCR and English language pack
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Prevent OpenMP thread contention and set Tessdata path for optimal cloud performance
ENV OMP_THREAD_LIMIT=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# Create non-root system user (appuser, UID 1000)
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend/ backend/
COPY frontend/ frontend/
COPY samples/ samples/
COPY README.md .

# Create data directory and assign ownership to appuser
RUN mkdir -p data/tokens data/profiles && \
    chown -R appuser:appuser /app

# Switch to unprivileged non-root user
USER appuser

# Expose default port
EXPOSE 8080

# Run uvicorn honoring cloud host $PORT and reverse proxy headers
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
