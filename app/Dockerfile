FROM python:3.14.6-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid app --create-home --home-dir /home/app app

COPY requirements.txt ./
RUN python -m pip install --requirement requirements.txt

COPY src/ ./src/
RUN chown -R app:app /app

USER app
EXPOSE 8080

CMD ["gunicorn", "--bind=0.0.0.0:8080", "--workers=1", "--threads=2", "--timeout=30", "--access-logfile=-", "--error-logfile=-", "csv_processor.wsgi:app"]
