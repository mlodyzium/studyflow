FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY . .
RUN chmod +x /app/docker/entrypoint.sh && \
    addgroup --system studyflow && \
    adduser --system --ingroup studyflow studyflow && \
    chown -R studyflow:studyflow /app

USER studyflow

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
