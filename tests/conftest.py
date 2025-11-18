from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STUBS = ROOT / "tests" / "stubs"
use_stub_dependencies = os.getenv("USE_FASTAPI_STUB", "1") != "0"
if use_stub_dependencies and str(STUBS) not in sys.path:
    sys.path.insert(0, str(STUBS))
