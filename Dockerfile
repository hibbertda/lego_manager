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

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:8000", "--workers", "2", "wsgi:app"]
