FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
RUN pip install uv && uv sync --frozen

# Copy agent service code
COPY src/agent_service/ ./src/agent_service/
COPY src/agent/ ./src/agent/
COPY src/config.py ./src/config.py

# temporarily until we deploy full db
COPY src/data/ ./src/data/

RUN mkdir -p /tmp

EXPOSE 8080

ENV PYTHONPATH=/app/src

CMD ["uv", "run", "python", "src/agent_service/main.py"]
