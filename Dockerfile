FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# gosu lets the entrypoint drop from root to appuser after fixing ownership
# of bind-mounted paths (see docker-entrypoint.sh) — more reliable for a
# self-hosted app than requiring the operator to pre-chown host paths.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --home-dir /home/appuser appuser \
    && chown -R appuser:appuser /app \
    && chmod +x docker-entrypoint.sh

ENV FLASK_DEBUG=0
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/login', timeout=3)" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
# --threads + --worker-class gthread: sync workers (the gunicorn default)
# handle exactly one request at a time each, so with only 2 workers, a
# single blocking outbound call (e.g. the OIDC token/userinfo exchange with
# an external IdP, or a slow Brickset API lookup) can tie up a worker for
# its full round-trip. A concurrent second request (health check, another
# user, a retried login) then has nowhere to go until a worker frees up,
# surfacing as connection refusals/timeouts through the reverse proxy.
# gthread gives each worker a small thread pool so those blocking calls no
# longer block the whole worker.
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "--timeout", "60", "wsgi:app"]
