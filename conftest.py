"""Pytest configuration for the repository.

Adds the backend package root to sys.path so tests can import the backend
modules consistently from the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))