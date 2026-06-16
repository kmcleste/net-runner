FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
COPY net_runner/ ./net_runner/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn net_runner.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
