FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
RUN pip install --upgrade pip \
    && python -c "import subprocess, sys, tomllib; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; subprocess.check_call([sys.executable, '-m', 'pip', 'install', *deps])"

COPY backend ./backend
COPY docker/backend-entrypoint.sh /usr/local/bin/orionstack-backend-entrypoint
RUN mkdir -p /app/default-storage \
    && cp -a /app/backend/app/storage/action_links /app/default-storage/action_links \
    && cp -a /app/backend/app/storage/dynamic_queries /app/default-storage/dynamic_queries \
    && chmod +x /usr/local/bin/orionstack-backend-entrypoint

WORKDIR /app/backend

EXPOSE 8000

ENTRYPOINT ["orionstack-backend-entrypoint"]
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
