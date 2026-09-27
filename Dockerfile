# Use official lightweight Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

# Install system dependencies including FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Set up non-root user 1000 for Hugging Face Spaces compatibility
RUN useradd -m -u 1000 user && \
    mkdir -p /app/temp_media /tmp/sonic_temp && \
    chmod -R 777 /app/temp_media /tmp/sonic_temp

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .
RUN chown -R user:user /app

USER user

# Expose port
EXPOSE 8000

# Start server
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
