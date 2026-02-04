.PHONY: help install dev run migrate shell test lint format clean docker-up docker-down celery

help:
	@echo "Available commands:"
	@echo "  install     - Install production dependencies"
	@echo "  dev         - Install development dependencies"
	@echo "  run         - Run development server"
	@echo "  migrate     - Run database migrations"
	@echo "  shell       - Open Django shell"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linter"
	@echo "  format      - Format code"
	@echo "  clean       - Remove cache files"
	@echo "  docker-up   - Start Docker containers"
	@echo "  docker-down - Stop Docker containers"
	@echo "  celery      - Run Celery worker"

install:
	pip install -r requirements/base.txt

dev:
	pip install -r requirements/dev.txt

run:
	cd src && python manage.py runserver

migrate:
	cd src && python manage.py migrate

makemigrations:
	cd src && python manage.py makemigrations

shell:
	cd src && python manage.py shell

createsuperuser:
	cd src && python manage.py createsuperuser

test:
	cd src && pytest --cov=taskqueue --cov-report=term-missing

lint:
	ruff check src/

format:
	ruff format src/

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".ruff_cache" -delete

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

celery:
	cd src && celery -A taskqueue worker -l info

celery-beat:
	cd src && celery -A taskqueue beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
