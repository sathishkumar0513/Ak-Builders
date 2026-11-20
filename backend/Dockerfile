FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

# libpq for psycopg, fonts for PDF rendering (₹ symbol support)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 fonts-dejavu-core postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh && useradd -m appuser && mkdir -p /app/media /app/staticfiles \
    && chown -R appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
# PORT is set by hosts such as Render; WEB_CONCURRENCY=1 + threads fits a 512 MB free instance.
# docker-compose sets WEB_CONCURRENCY=3 (it shares lockouts through Redis).
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-1} --threads ${GUNICORN_THREADS:-4} --timeout 120 --access-logfile -"]
