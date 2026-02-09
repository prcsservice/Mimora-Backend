# Auth Microservice Dockerfile
# For deploying to Google Cloud Run

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install system dependencies for PostgreSQL and other requirements
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY app/auth/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir psycopg2-binary httpx python-dotenv

# Copy the application code
COPY app/ ./app/
COPY serviceAccountKey.json ./serviceAccountKey.json

# Expose the port Cloud Run expects
EXPOSE 8080

# Run uvicorn on the port Cloud Run provides
CMD uvicorn app.auth.main:app --host 0.0.0.0 --port ${PORT:-8080}
