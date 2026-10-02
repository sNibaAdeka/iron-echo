"""Run from File > Execute Python Script after saving the project and level.

First run only. Replacing existing owned assets is deliberately not automatic.
This creates an ART sandbox, not a gameplay map or a complete game.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_art
import validate_import
import build_arena


def main():
    import_art.main([])
    report = validate_import.main([])
    if report["failed"]:
        raise RuntimeError("Import validation failed; inspect Saved/IronEchoArtReports/validate_import.json before building the arena")
    build_arena.main([])


if __name__ == "__main__":
    main()
