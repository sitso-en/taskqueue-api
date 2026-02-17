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
COPY bin/ bin/

WORKDIR /app/src

EXPOSE 8000

RUN chmod +x /app/bin/start-web.sh

CMD ["/app/bin/start-web.sh"]
