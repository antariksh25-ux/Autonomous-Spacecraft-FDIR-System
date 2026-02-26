"""Uvicorn entrypoint shim.

This file exists so you can run the backend with:

  uvicorn main:app --reload --port 8000

from the `FDIR/` directory.
"""

from __future__ import annotations

from backend.api import app
