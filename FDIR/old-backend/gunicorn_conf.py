from __future__ import annotations

import os


bind = f"0.0.0.0:{os.getenv('PORT', '8001')}"
worker_class = "uvicorn.workers.UvicornWorker"

# SQLite + optional simulator are not safe with many processes by default.
# You can increase this only after migrating persistence to a server DB
# and disabling simulation.
workers = int(os.getenv("WEB_CONCURRENCY", "1") or "1")

loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "-"
errorlog = "-"

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60") or "60")
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5") or "5")
