FROM python:3.11-slim

WORKDIR /app

# ── PYTHONPATH: makes every absolute import resolve from /app ──────────────
# This is the root fix for "ModuleNotFoundError: No module named 'services'"
ENV PYTHONPATH=/app

# System deps for PyMuPDF and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source packages that contain absolute imports
COPY services/app/         ./services/app/
COPY services/supervisor/  ./services/supervisor/
COPY services/agents/      ./services/agents/
COPY services/mcp_server/  ./services/mcp_server/
COPY ingestion/            ./ingestion/
COPY evaluation/           ./evaluation/
COPY monitoring/           ./monitoring/
COPY data/                 ./data/

# Top-level __init__.py so 'services' is a proper package
RUN touch ./services/__init__.py

# Pre-create runtime directories
RUN mkdir -p /app/data/uploads /app/vector_store /app/logs

EXPOSE 8501 8080

# Run Streamlit from WORKDIR so all relative paths resolve to /app
CMD ["streamlit", "run", "services/app/streamlit_app.py", \
     "--server.port", "8501", \
     "--server.address", "0.0.0.0", \
     "--server.headless", "true"]
