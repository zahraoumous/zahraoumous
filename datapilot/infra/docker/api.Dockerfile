FROM python:3.12.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libseccomp2 \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir uv==0.12.23
COPY --chmod=644 pyproject.toml uv.lock ./
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca UV_SYSTEM_CERTS=true; fi; \
    uv sync --frozen --no-dev
COPY --chown=10001:10001 services ./services
COPY --chown=10001:10001 alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/services/api:/app/services/worker"
USER 10001:10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
