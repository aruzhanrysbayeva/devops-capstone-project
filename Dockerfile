FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 1000 --gid 0 --create-home theia
COPY service ./service
RUN chown -R 1000:0 /app && chmod -R g=u /app

USER 1000
EXPOSE 8080
CMD ["gunicorn", "--bind=0.0.0.0:8080", "--log-level=info", "--access-logfile=-", "--error-logfile=-", "service:app"]
