"""Pytest configuration for backend tests.

Ensures the backend package layout is importable when pytest is launched from
the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))