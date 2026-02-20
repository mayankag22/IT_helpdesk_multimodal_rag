FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic RestrictedPython python-dotenv httpx

COPY services/mcp_server/ ./services/mcp_server/

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "services.mcp_server.server:app", "--host", "0.0.0.0", "--port", "8000"]
