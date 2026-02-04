# TaskQueue API

A production-grade distributed task queue system built with Django REST Framework, Celery, and Redis.

![CI](https://github.com/sitso-en/taskqueue-api/actions/workflows/ci.yml/badge.svg)

## Features

- **Async Task Processing** - Celery + Redis for reliable background job execution
- **Real-time Updates** - WebSocket support for live task status
- **Rate Limiting** - Built-in request throttling
- **Dead Letter Queue** - Failed tasks are preserved for debugging and reprocessing
- **Priority Queues** - Tasks can be prioritized (Low, Normal, High, Critical)
- **Scheduled Tasks** - Schedule tasks for future execution
- **Retry Logic** - Configurable retry with exponential backoff
- **Admin Dashboard** - Full Django admin integration
- **Prometheus Metrics** - Built-in monitoring endpoint

## Tech Stack

- Python 3.12+
- Django 5.0+
- Django REST Framework
- Celery 5.3+
- Redis 7+
- PostgreSQL 16+
- Channels (WebSockets)

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/sitso-en/taskqueue-api.git
cd taskqueue-api

# Copy environment file
cp .env.example .env

# Start all services
docker compose up -d

# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser
```

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
make dev

# Start PostgreSQL and Redis (or use Docker for just these)
docker compose up -d db redis

# Copy environment file
cp .env.example .env

# Run migrations
make migrate

# Create superuser
make createsuperuser

# Run the development server
make run

# In another terminal, start Celery worker
make celery
```

## API Endpoints

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tasks/` | List all tasks |
| POST | `/api/v1/tasks/` | Create a new task |
| GET | `/api/v1/tasks/{id}/` | Get task details |
| POST | `/api/v1/tasks/{id}/cancel/` | Cancel a task |
| POST | `/api/v1/tasks/{id}/retry/` | Retry a failed task |
| GET | `/api/v1/tasks/stats/` | Get task statistics |

### Dead Letter Queue

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/dead-letters/` | List dead letter entries |
| GET | `/api/v1/dead-letters/{id}/` | Get entry details |
| POST | `/api/v1/dead-letters/{id}/reprocess/` | Reprocess entry |

### WebSocket

Connect to `ws://localhost:8000/ws/tasks/{task_id}/` to receive real-time updates for a specific task.

## Task Types

| Type | Description | Payload |
|------|-------------|---------|
| `echo` | Returns the payload as-is | Any JSON |
| `compute` | Performs mathematical operations | `{"operation": "sum\|product\|average", "numbers": [1,2,3]}` |
| `sleep` | Simulates long-running task | `{"duration": 10}` |
| `http_request` | Makes HTTP request | `{"url": "https://..."}` |
| `process_data` | Processes data arrays | `{"data": [...], "operation": "transform\|filter\|aggregate"}` |

## Example Usage

### Create a Task

```bash
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Computation",
    "task_type": "compute",
    "payload": {
      "operation": "sum",
      "numbers": [1, 2, 3, 4, 5]
    },
    "priority": 10
  }'
```

### Check Task Status

```bash
curl http://localhost:8000/api/v1/tasks/{task_id}/
```

### Get Statistics

```bash
curl http://localhost:8000/api/v1/tasks/stats/
```

## Monitoring

- **Prometheus metrics**: `GET /metrics`
- **Admin dashboard**: `http://localhost:8000/admin/`

## Project Structure

```
taskqueue-api/
├── .github/workflows/    # CI/CD and streak reminder
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── src/
│   └── taskqueue/
│       ├── apps/
│       │   ├── core/         # Rate limiting, middleware
│       │   └── tasks/        # Task models, views, Celery tasks
│       ├── settings/
│       └── ...
└── tests/
```

## Running Tests

```bash
make test
```

## License

MIT
