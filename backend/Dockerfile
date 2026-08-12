FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

RUN pip install --no-cache-dir -e .

# Run as an unprivileged user -- if a dependency or code-level RCE is ever
# found, this caps the blast radius at "this container" rather than handing
# an attacker root inside it. media/ is the one directory the app writes to
# at runtime (LocalDiskStorage), so it needs to be owned by that user.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/media \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
