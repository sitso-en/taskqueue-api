FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

# Copy application
COPY src/ src/

WORKDIR /app/src

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "taskqueue.asgi:application"]
