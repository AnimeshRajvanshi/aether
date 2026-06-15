"""Put the tools/ directory on sys.path so tests can import the standalone
verifier module (tools/ is a scripts dir, not an installed package)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
