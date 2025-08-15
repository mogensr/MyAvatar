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
ENV PORT=8080

# Expose the hardcoded port
EXPOSE 8080

# Copy start script to the container
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Use the start script
CMD ["/bin/bash", "/app/start.sh"]
