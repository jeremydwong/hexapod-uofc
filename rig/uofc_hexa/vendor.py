"""The one place that knows where the Motion Systems ForceSeatDI SDK bindings live.

code/, plugins/ and examples/ at the repo root are the vendor SDK as shipped and are
never edited. Two ways to reach the vendor's Python bindings:

- Installed from git or a wheel: the build copies code/ForceSeatDI_Structs.py and
  code/ForceSeatDI_Defines.py into uofc_hexa/_sdk/ (pyproject.toml, force-include).
- Editable install in this repo (uv sync): no _sdk/, so they are read from code/.

The native library (ForceSeatDI64.dll / .so) is never bundled; pass --library or set
$FORCESEATDI_LIBRARY.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys

BUNDLED_SDK = Path(__file__).resolve().parent / "_sdk"
REPO_SDK = Path(__file__).resolve().parents[2] / "code"  # rig/uofc_hexa/vendor.py -> repo root
LIBRARY_ENV = "FORCESEATDI_LIBRARY"


def sdk_dir():
    """Folder holding ForceSeatDI_Structs.py: the bundled copy if present, else the repo's code/."""
    for folder in (BUNDLED_SDK, REPO_SDK):
        if (folder / "ForceSeatDI_Structs.py").exists():
            return folder
    raise FileNotFoundError(f"ForceSeatDI Python bindings not found in {BUNDLED_SDK} or {REPO_SDK}")


def structs():
    """Return the vendor's ForceSeatDI_Structs module (packed ctypes structures).

    The vendor module imports ForceSeatDI_Defines by bare name, so its folder goes on sys.path.
    """
    folder = str(sdk_dir())
    if folder not in sys.path:
        sys.path.insert(0, folder)
    return importlib.import_module("ForceSeatDI_Structs")


def default_library():
    """The native library path from $FORCESEATDI_LIBRARY, or None if it is unset."""
    return os.environ.get(LIBRARY_ENV) or None
