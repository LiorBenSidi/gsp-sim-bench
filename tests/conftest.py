"""Path bootstrap so tests import the modular package and the grader fixtures uninstalled."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "src", ROOT / "fixtures"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
