"""Lower the platform from wherever it is (level, near centre) to the park height, then Park.

For recovering after a fault left it paused up in the air: `uv run kneel`.
"""
import argparse
import ctypes as ct
import time

import numpy as np

from uofc_hexa import vendor
from uofc_hexa.hexapod import level_move as lm
from uofc_hexa.hexapod import test_from_park as tfp


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--library", default=vendor.default_library(), required=not vendor.default_library())
    parser.add_argument("--serial", default="any")
    parser.add_argument("--run-byte", type=int, choices=[0, 1], default=0)
    parser.add_argument("--rate", type=float, default=50.0, help="peak lowering speed, mm/s (165 mm: ~6 s at 50)")
    args = parser.parse_args()

    d = lm.Device(args.library, None, args.serial, args.run_byte, 2000, 0, tfp.LIFT_BOUND_MM)
    try:
        start, rpy, _, state = tfp.lenient_read(d)
        print(f"Start: pose {np.round(start, 2)} mm, rpy {np.round(np.rad2deg(rpy), 3)} deg, state=0x{state:x}")
        if np.max(np.abs(start[:2])) > 5 or np.max(np.abs(np.rad2deg(rpy))) > 0.5:
            raise SystemExit("Not near centre and level; not lowering")
        target = np.array([0.0, 0.0, tfp.LOWEST_HEAVE_MM])
        clock0 = time.monotonic()
        last = tfp.stream(d, start, target, args.rate, "kneel", lambda: time.monotonic() - clock0, [], [], hold=1.0)
        d.send(last, pause=True)
        park = d.lib.ForceSeatDI_Park
        park.restype, park.argtypes = ct.c_char, [ct.c_void_p, ct.c_uint8]
        print(f"Park request: {'ok' if park(d.api, 0) == b'\x01' else 'FAILED'}")
        time.sleep(3)
        end, _, _, state = tfp.lenient_read(d)
        print(f"End: pose {np.round(end, 2)} mm, state=0x{state:x}")
    finally:
        d.close()


if __name__ == "__main__":
    main()
