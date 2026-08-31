"""WSGI entrypoint. For local development, run: python wsgi.py
For production, run with gunicorn: gunicorn -b 0.0.0.0:8000 wsgi:app
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
