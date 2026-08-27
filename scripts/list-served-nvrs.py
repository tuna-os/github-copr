#!/usr/bin/env python3
"""Print NAME-VERSION-RELEASE for every package a published rpm-md index serves.

    list-served-nvrs.py https://repo.tunaos.org/hummingbird/20251124-x86_64/

Output feeds `build-chain.sh --served-nvrs`: one NVR per line, deduplicated.
Epoch is deliberately dropped -- the skip compares against `rpmspec
--queryformat %{NAME}-%{VERSION}-%{RELEASE}`, which has no epoch either.

An unreachable or empty index prints nothing and exits 0: a first publish
legitimately has nothing served, and the caller must build, not crash.
"""

from __future__ import annotations

import gzip
import re
import subprocess
import sys


def fetch(url: str) -> bytes:
    # curl, not urllib: the CI egress proxy 403s urllib's requests.
    run = subprocess.run(["curl", "-sfL", "--max-time", "120", url],
                         capture_output=True)
    if run.returncode != 0:
        return b""
    return run.stdout


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    base = sys.argv[1].rstrip("/")
    repomd = fetch(f"{base}/repodata/repomd.xml").decode(errors="replace")
    m = re.search(r'href="(repodata/[^"]*primary\.xml[^"]*)"', repomd)
    if not m:
        return
    raw = fetch(f"{base}/{m.group(1)}")
    if not raw:
        return
    if m.group(1).endswith(".gz"):
        raw = gzip.decompress(raw)
    data = raw.decode(errors="replace")
    seen = set()
    for pkg in re.finditer(
        r'<name>([^<]+)</name>.*?ver="([^"]+)" rel="([^"]+)"', data, re.S
    ):
        nvr = f"{pkg.group(1)}-{pkg.group(2)}-{pkg.group(3)}"
        if nvr not in seen:
            seen.add(nvr)
            print(nvr)


if __name__ == "__main__":
    main()
