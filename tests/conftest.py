import sys
from pathlib import Path

# examples/ modules (arm_dance, voice) are scripts, not a package — put them on the path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))
