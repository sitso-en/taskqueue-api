# TaskQueue API

A production-grade distributed task queue system built with Django REST Framework, Celery, and Redis.

![CI](https://github.com/sitso-en/taskqueue-api/actions/workflows/ci.yml/badge.svg)

## Features

- **JWT Authentication** - Secure API access with token-based auth
- **Async Task Processing** - Celery + Redis for reliable background job execution
- **Real-time Updates** - WebSocket support for live task status
- **Rate Limiting** - Built-in request throttling
- **Dead Letter Queue** - Failed tasks are preserved for debugging and reprocessing
- **Priority Queues** - Tasks can be prioritized (Low, Normal, High, Critical) and are routed to dedicated Celery queues (`low`, `default`, `high`, `critical`)
- **Scheduled Tasks** - Schedule tasks for future execution
- **Retry Logic** - Configurable retry with exponential backoff
- **Admin Dashboard** - Full Django admin integration
- **Prometheus Metrics** - Built-in monitoring endpoint
- **Webhook Delivery History** - Persist delivery attempts and allow replay

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
# If you're upgrading from an older setup that ran without migrations, use: --fake-initial
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
# If you're upgrading from an older setup that ran without migrations, use: python manage.py migrate --fake-initial
make migrate

# Create superuser
make createsuperuser

# Run the development server
make run

# In another terminal, start Celery worker
make celery
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register/` | Register a new user |
| POST | `/api/v1/auth/token/` | Login and get JWT tokens |
| POST | `/api/v1/auth/token/refresh/` | Refresh access token |
| POST | `/api/v1/auth/token/verify/` | Verify a token |
| POST | `/api/v1/auth/logout/` | Logout (blacklist refresh token) |
| GET | `/api/v1/auth/profile/` | Get current user profile |
| PATCH | `/api/v1/auth/profile/` | Update current user profile |
| POST | `/api/v1/auth/change-password/` | Change password |

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

## Webhooks (Task Callbacks)

You can attach a webhook URL to a task. When the task **succeeds**, **fails**, or is **revoked**, TaskQueue will POST a JSON payload to your callback.

### Configure on task creation

Send these optional fields in `POST /api/v1/tasks/`:
- `callback_url` (string)
- `callback_events` (list of strings; defaults to `["task.succeeded", "task.failed", "task.revoked"]` when `callback_url` is provided)
- `callback_headers` (object of string:string)
- `callback_secret` (string; used to sign payload)
- `callback_max_attempts` (int; default 5)

### Security

If `callback_secret` is set, requests include:
- `X-Taskqueue-Signature`: HMAC-SHA256 hex digest of the raw request body

### Delivery history + replay

Each webhook enqueue creates a `WebhookDelivery` record.

Endpoints:
- `GET /api/v1/tasks/{task_id}/webhook-deliveries/` (list deliveries)
- `POST /api/v1/tasks/{task_id}/webhook-deliveries/{delivery_id}/replay/` (replay)

The debug endpoint `POST /api/v1/tasks/{task_id}/trigger_webhook/` returns `delivery_id` when a delivery was enqueued.

### Example payload

```json
{
  "event": "task.succeeded",
  "sent_at": "2026-02-08T12:00:00+00:00",
  "task": {
    "id": "...",
    "name": "My Task",
    "task_type": "compute",
    "status": "success",
    "priority": 10,
    "queue": "high",
    "payload": {"operation": "sum", "numbers": [1,2,3]},
    "result": {"operation": "sum", "result": 6},
    "error_message": "",
    "created_at": "...",
    "started_at": "...",
    "completed_at": "...",
    "tags": [],
    "metadata": {}
  }
}
```

## Task Types

| Type | Description | Payload |
|------|-------------|---------|
| `echo` | Returns the payload as-is | Any JSON |
| `compute` | Performs mathematical operations | `{"operation": "sum\|product\|average", "numbers": [1,2,3]}` |
| `sleep` | Simulates long-running task | `{"duration": 10}` |
| `http_request` | Makes HTTP request | `{"url": "https://..."}` |
| `process_data` | Processes data arrays | `{"data": [...], "operation": "transform\|filter\|aggregate"}` |
| `send_email` | Sends an email (simulated) | `{"to": "user@example.com", "subject": "Hello", "body": "..."}` |
| `resize_image` | Resizes an image (simulated) | `{"image_url": "https://...", "width": 800, "height": 600, "format": "jpeg"}` |
| `generate_report` | Generates a report (simulated) | `{"report_type": "summary\|detailed\|analytics\|financial", "output_format": "json\|csv\|pdf\|xlsx"}` |

## Example Usage

### Register a User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "myuser",
    "email": "myuser@example.com",
    "password": "securepassword123",
    "password_confirm": "securepassword123"
  }'
```

### Login and Get Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "myuser",
    "password": "securepassword123"
  }'
```

### Create a Task (with Auth)

```bash
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_access_token>" \
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
curl http://localhost:8000/api/v1/tasks/{task_id}/ \
  -H "Authorization: Bearer <your_access_token>"
```

### Get Statistics

```bash
curl http://localhost:8000/api/v1/tasks/stats/ \
  -H "Authorization: Bearer <your_access_token>"
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
