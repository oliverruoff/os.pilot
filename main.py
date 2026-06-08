from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ospilot.app import main


if __name__ == "__main__":
    raise SystemExit(main())
