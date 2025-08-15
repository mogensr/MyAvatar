FROM python:3.11-slim

# Install system dependencies for core application
RUN apt-get update && apt-get install -y --no-install-recommends \
    # OpenGL libraries for OpenCV (updated for Debian Trixie)
    libgl1-mesa-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    # Curl for healthcheck
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=debug
ENV PORT=8080

# Expose the hardcoded port
EXPOSE 8080

# Copy start script and make executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# EMERGENCY FIX: Correct Railway deployment command
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

# Add Docker healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
