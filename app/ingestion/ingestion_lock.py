"""Serialize heavy ingestion DB work so SQLite is not written from multiple threads at once.

Manual sync, auto-sync, and batch re-parse can otherwise interleave commits and raise
``OperationalError: database is locked`` even with WAL/busy_timeout.
"""
from __future__ import annotations

import threading

ingestion_write_lock = threading.Lock()
