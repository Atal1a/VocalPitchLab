"""Run VocalPitchLab from a source checkout or packaged application."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vocalpitchlab.__main__ import main

if __name__ == '__main__':
    raise SystemExit(main())
