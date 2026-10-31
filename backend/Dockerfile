FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY ctrlz ./ctrlz
RUN uv sync --frozen --no-dev --no-editable && useradd --uid 10001 --create-home ctrlz && mkdir /data && chown ctrlz /data
USER ctrlz
ENV PATH=/app/.venv/bin:$PATH DATABASE_URL=sqlite:////data/ctrlz.db DATA_DIR=/data RUNBOOK_DIR=/runbooks CREWAI_STORAGE_DIR=/data/crewai CREWAI_TELEMETRY_ENABLED=false OTEL_SDK_DISABLED=true PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["uvicorn", "ctrlz.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
