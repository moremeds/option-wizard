import sys
from pathlib import Path

SKILL_ROOT = (
    Path(__file__).resolve().parent.parent
    / "plugins"
    / "option-wizard"
    / "skills"
    / "option-wizard"
)
sys.path.insert(0, str(SKILL_ROOT))
