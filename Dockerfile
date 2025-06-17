FROM python:3.11-slim

# Install system dependencies including OpenGL libraries for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
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

# Create a simple shell script that handles PORT properly
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'PORT="${PORT:-8000}"' >> /app/start.sh && \
    echo 'echo "Starting application on port: $PORT"' >> /app/start.sh && \
    echo 'exec python -m uvicorn main:app --host 0.0.0.0 --port "$PORT"' >> /app/start.sh && \
    chmod +x /app/start.sh

# Run the script
CMD ["/app/start.sh"]
