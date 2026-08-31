FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a dedicated non-root user rather than the container default root,
# so a code-execution bug in the app (or a vulnerable dependency) can't
# trivially escalate to root inside the container.
RUN useradd --system --create-home --home-dir /home/appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV FLASK_DEBUG=0
EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "--workers", "2", "wsgi:app"]
