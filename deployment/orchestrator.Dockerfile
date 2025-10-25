FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
RUN pip install uv && uv sync --frozen

# Copy only orchestrator code
COPY src/orchestrator/ ./src/orchestrator/
COPY src/config.py ./src/config.py

RUN mkdir -p /tmp

EXPOSE 8000

ENV PORT=8000
ENV PYTHONPATH=/app/src

CMD ["uv", "run", "python", "src/orchestrator/main.py"]
