FROM python:3.12-alpine AS builder

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt
RUN pip uninstall -y pip \
    && find /opt/venv -type d \( -name test -o -name tests -o -name __pycache__ \) -prune -exec rm -rf '{}' + \
    && find /opt/venv -type f -name '*.pyc' -delete

FROM python:3.12-alpine AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SQLITE_PATH=/data/loja.db

RUN addgroup -S app && adduser -S -G app app \
    && mkdir -p /data \
    && chown app:app /data

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app static ./static

USER app
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "app:api", "--host", "0.0.0.0", "--port", "8000"]