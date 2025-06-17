FROM python:3.11-slim

# Install system dependencies including OpenGL libraries
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
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Add startup script and make it executable
COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh

# Run the application using bash
CMD ["/bin/bash", "/app/startup.sh"]
