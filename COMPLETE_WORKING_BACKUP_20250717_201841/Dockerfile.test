FROM python:3.11-slim

WORKDIR /app

# Install only the necessary dependencies
RUN pip install --no-cache-dir fastapi uvicorn

# Copy just the test application
COPY app_test.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Start the application directly (no shell script)
CMD ["python", "-m", "uvicorn", "app_test:app", "--host", "0.0.0.0", "--port", "8080"]
