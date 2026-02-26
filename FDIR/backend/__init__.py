"""FDIR backend package.

This backend is ingestion-first:
- It does not generate telemetry.
- It processes telemetry samples pushed in via REST.
- It streams computed system snapshots via WebSocket.
"""
