"""
Pytest bootstrap: ensure config.ini exists before any test module is imported.

Tests transitively import src/common/common.py, which instantiates Config() at
module load and reads config.ini from the repo root. Without this file, every
test errors out during collection. This conftest copies scripts/config.ini.example
into place if no config.ini exists yet, so a fresh checkout (and CI) can run
the test suite without a manual setup step.

A locally-customized config.ini is never overwritten.
"""
import shutil
from pathlib import Path

_root = Path(__file__).resolve().parent
_config = _root / "config.ini"
_example = _root / "scripts" / "config.ini.example"

if not _config.exists() and _example.exists():
    shutil.copyfile(_example, _config)
