#!/usr/bin/env python3
"""RFC 011's target-parameterized gap-engine entry point.

The implementation remains in measure-hummingbird-gap.py while Hummingbird
is the first converted family. Keeping its tested closure and tiering code in
one place is intentional: this command supplies the target contract, and new
targets become configuration plus a roots manifest rather than forked scripts.

Usage:
    scripts/measure-target-gap.py --target hummingbird \
      --report-json docs/hummingbird-desktop-gap.json \
      --build-order build-order-hummingbird-desktops.yml
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys


HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "measure_hummingbird_gap", HERE / "measure-hummingbird-gap.py"
)
_engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_engine)


def main() -> None:
    if "--target" not in sys.argv:
        raise SystemExit("measure-target-gap.py requires --target")
    _engine.main()


if __name__ == "__main__":
    main()
