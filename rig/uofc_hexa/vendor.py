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
    """$FORCESEATDI_LIBRARY, else the newest ~/Documents/MotionSystems/ForceSeatDI_*/ForceSeatDI64.dll
    (where the lab PC has it), else None."""
    if os.environ.get(LIBRARY_ENV):
        return os.environ[LIBRARY_ENV]
    found = sorted((Path.home() / "Documents" / "MotionSystems").glob("ForceSeatDI_*/ForceSeatDI64.dll"))
    return str(found[-1]) if found else None


MS_SERVICES = ("MotionSystems Com64", "MotionSystems AppWatcher64")


def running_ms_services():
    """Motion Systems' ForceSeatPM services that are running (Windows only; [] elsewhere).

    They share the platform's USB link with our ForceSeatDI connection, and come back on their
    own (seen after a USB replug, 2026-10-21); stop_ms_processes.bat stops them.
    """
    if sys.platform != "win32":
        return []
    import subprocess
    running = []
    for name in MS_SERVICES:
        out = subprocess.run(["sc", "query", name], capture_output=True, text=True).stdout
        if "RUNNING" in out:
            running.append(name)
    return running


PLATFORM_USB_ID = r"USB\VID_0483&PID_A110\*"  # ForceSeatMP1 controllers (PS-6TL-350, M10)


def reset_platform_usb():
    """Re-enumerate the controller's USB device: revives a dead SDK readback (error 2).

    pnputil /remove-device + /scan-devices = a software replug (~1 s). Needs Administrator and no
    open ForceSeatDI handle (close the Device first; Motion Systems services stopped), else Windows
    defers it to a reboot. Without admin, prints the commands instead. Returns True if it ran.
    """
    if sys.platform != "win32":
        return False
    import ctypes
    import subprocess
    ps = ["powershell", "-NoProfile", "-Command"]
    ids = subprocess.run(ps + [f"(Get-PnpDevice -PresentOnly -InstanceId '{PLATFORM_USB_ID}').InstanceId"],
                         capture_output=True, text=True).stdout.split()
    if not ids:
        print("USB reset: no controller present; replug its USB cable")
        return False
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("USB reset needs Administrator. In an admin PowerShell (or replug the cable):")
        for i in ids:
            print(f'  pnputil /remove-device "{i}"')
        print("  pnputil /scan-devices")
        return False
    for i in ids:
        out = subprocess.run(["pnputil", "/remove-device", i], capture_output=True, text=True).stdout
        print("USB reset:", " ".join(out.split())[-120:])
    out = subprocess.run(["pnputil", "/scan-devices"], capture_output=True, text=True).stdout
    print("USB reset:", " ".join(out.split())[-80:])
    return True
