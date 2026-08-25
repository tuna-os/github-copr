#!/usr/bin/env python3
"""Report which factory targets upstream has moved past since we last measured.

Hummingbird's whole reason for existing is shipping fixes as soon as they are
published — near-zero CVE, per-package lifecycle, rolling with Rawhide. A
factory that measures its gap against a snapshot taken weeks ago cannot serve
that: it keeps rebuilding packages upstream has already adopted, and does not
know about the ones it has not.

`manifests/package-factory.yaml` already declares what to do about this, per
target:

    gap_measurement:
      target_index: https://.../public-hummingbird/$arch/
      drift:
        mode: propose
        build_order: build-order-hummingbird-desktops.yml
        report_json: docs/hummingbird-desktop-gap.json

Nothing implemented it. `.github/workflows/hummingbird-gap-drift.yml` used to,
watching the upstream repomd revision and re-measuring when it changed, and was
removed in 6d4b77a ("de-hardcode the pipeline from hummingbird", #517) along
with everything else hummingbird-specific. The SCRIPT it drove
(measure-target-gap.py) was correctly generalised and kept; the reactive driver
was not replaced, so the declaration above has been inert since.

This is that driver, generic over targets rather than a restored copy: it reads
the manifest and checks every target declaring `gap_measurement.drift`, so a
second target opting in needs no change here.

Measured while writing this, against the live index:

    live upstream revision   1787625027   2026-08-25T02:30:27Z
    committed measurement    1787045128   2026-08-18T09:25:28Z

Upstream had published five hours earlier and nothing in this repository knew.

Exit status is 0 whether or not anything drifted — "upstream moved" is a normal
event, not a failure. Callers read the report or --github-output. Exit 2 is
reserved for being unable to tell (network/parse), because silently reporting
"no drift" when the check could not run is the failure this file exists to
prevent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

MANIFEST = Path("manifests/package-factory.yaml")

# The modes upstream-drift.yml actually implements. `propose` opens a pull
# request with the regenerated measurement; there is deliberately no
# `apply`, because committing a machine-regenerated build order straight
# to main is a policy call rather than a missing feature.
IMPLEMENTED_MODES = {"propose"}
REPOMD_NS = "{http://linux.duke.edu/metadata/repo}"
TIMEOUT = 45
UA = {"User-Agent": "tunaos-upstream-drift (+https://github.com/tuna-os/tunaos-packages)"}

# What the manifest's `$arch` placeholder resolves to when probing. The revision
# is a property of the published repository as a whole, so one arch is enough to
# answer "has upstream moved"; measuring is what needs every arch.
PROBE_ARCH = "x86_64"


def fetch_revision(index_url: str, opener=None) -> str | None:
    """The <revision> of index_url's repomd.xml, or None if it cannot be read.

    `opener` is injectable so the tests never touch the network — a drift check
    that can only be exercised against a live server is one nobody runs.
    """
    url = index_url.rstrip("/") + "/repodata/repomd.xml"
    try:
        if opener is not None:
            body = opener(url)
        else:
            req = urllib.request.Request(url, headers=UA, method="GET")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read()
        return ET.fromstring(body).findtext(f"{REPOMD_NS}revision")
    except (urllib.error.URLError, OSError, ET.ParseError):
        return None


def recorded_revision(report_json: str | os.PathLike) -> str | None:
    """The upstream revision the last committed measurement was taken against."""
    try:
        with open(report_json, encoding="utf-8") as f:
            return json.load(f).get("target_index", {}).get("revision")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def drift_targets(manifest: dict) -> list[tuple[str, dict]]:
    """(name, gap_measurement) for every target declaring a drift block."""
    out = []
    for name, spec in (manifest.get("targets") or {}).items():
        if not isinstance(spec, dict):
            continue
        gap = spec.get("gap_measurement")
        if isinstance(gap, dict) and isinstance(gap.get("drift"), dict):
            out.append((name, gap))
    return out


def evaluate(manifest: dict, opener=None, arch: str = PROBE_ARCH) -> list[dict]:
    results = []
    for name, gap in drift_targets(manifest):
        index = str(gap.get("target_index", "")).replace("$arch", arch)
        report = gap["drift"].get("report_json")
        live = fetch_revision(index, opener=opener) if index else None
        seen = recorded_revision(report) if report else None
        if live is None:
            # The live index could not be read. This is the state that must
            # never be reported as "no drift": a failed check that reads as
            # current is exactly how a stale measurement survives unnoticed.
            state = "unknown"
        elif seen is None:
            # Declared but never measured — fedora is in this state today, with
            # a report_json that has never been written. Not an error and not
            # drift; it means the first measurement has yet to happen, and
            # calling it "unknown" would make a real fetch failure invisible
            # among the not-yet-started ones.
            state = "unmeasured"
        elif str(live) != str(seen):
            state = "drifted"
        else:
            state = "current"
        # A declared mode nothing implements is worse than no declaration.
        # upstream-drift.yml always PROPOSES -- it opens a pull request with
        # the regenerated measurement -- so `mode: apply` would read as
        # "commit it straight to main" and silently do the opposite. That is
        # the third inert declaration found in this factory in one day (the
        # drift driver itself, and MOCK_CACHE_DIR), and all three were silent
        # for the same reason: nothing failed.
        mode = gap["drift"].get("mode")
        if mode not in IMPLEMENTED_MODES:
            # Reported per target, NOT raised. One target declaring a mode
            # nothing implements must not stop the others from being
            # measured -- that is the same shape as the unreadable-index
            # case this workflow already handles, and swallowing every
            # target because one is misdeclared is how a reactive detector
            # stops reacting.
            state = "unimplemented-mode"
        results.append({
            "target": name,
            "state": state,
            "live": live,
            "recorded": seen,
            "index": index,
            "mode": mode,
            "build_order": gap["drift"].get("build_order"),
            "report_json": report,
        })
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--target", help="check only this target")
    ap.add_argument("--github-output", action="store_true",
                    help="append drifted=<csv>, any=<bool> and matrix=<json> "
                         "to $GITHUB_OUTPUT")
    ap.add_argument("--force-all", action="store_true",
                    help="emit every declared target in the matrix regardless "
                         "of drift (for a deliberate re-measure)")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    results = evaluate(manifest)
    if args.target:
        results = [r for r in results if r["target"] == args.target]

    if not results:
        # No declaration means nothing to watch, which is a legitimate state —
        # but it is indistinguishable from "the manifest shape changed and this
        # reads nothing", so say which.
        print("::warning::no target declares gap_measurement.drift — "
              "nothing is watching upstream")

    unknown = 0
    misdeclared = 0
    for r in results:
        if r["state"] == "drifted":
            print(f"DRIFTED  {r['target']:22s} upstream={r['live']} "
                  f"measured={r['recorded']}  {r['index']}")
        elif r["state"] == "current":
            print(f"current  {r['target']:22s} revision={r['live']}")
        elif r["state"] == "unmeasured":
            print(f"unmeasured {r['target']:20s} upstream={r['live']} — "
                  f"no committed measurement at {r['report_json']} yet")
        elif r["state"] == "unimplemented-mode":
            misdeclared += 1
            print(f"MISDECLARED {r['target']:19s} mode={r['mode']!r}")
            print(f"::error::{r['target']} declares "
                  f"gap_measurement.drift.mode={r['mode']!r}, which nothing "
                  f"implements (implemented: "
                  f"{', '.join(sorted(IMPLEMENTED_MODES))}). The manifest "
                  "describes behaviour the factory does not have, so this "
                  "target is not re-measured.")
        else:
            unknown += 1
            print(f"UNKNOWN  {r['target']:22s} live={r['live']} "
                  f"recorded={r['recorded']}  {r['index']}")
            print(f"::error::cannot determine drift for {r['target']} — "
                  "treating this as unknown rather than 'no drift', because "
                  "reporting no drift from a failed check is how a stale "
                  "measurement survives")

    drifted = [r["target"] for r in results if r["state"] == "drifted"]
    # --force-all exists because a `force` dispatch input that produces an
    # EMPTY matrix is a button that silently does nothing: the job is skipped
    # for having no cells, and the run goes green having measured no target.
    # Forcing means "measure regardless of the revision gate", so the matrix
    # has to be every declared target, not the drifted subset.
    # A misdeclared target is excluded even under --force-all: the driver
    # cannot honour the mode it asks for, so re-measuring it would
    # produce an outcome the manifest does not describe.
    forced = [r["target"] for r in results
              if r["state"] != "unimplemented-mode"]
    selected = forced if args.force_all else drifted
    if args.github_output and (path := os.environ.get("GITHUB_OUTPUT")):
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"drifted={','.join(drifted)}\n")
            f.write(f"any={'true' if selected else 'false'}\n")
            # A ready-made JSON array for `matrix: fromJSON(...)`. Built here
            # rather than assembled from a CSV in workflow expression syntax:
            # GitHub Actions has no replace()/split(), and an invalid
            # expression fails the WHOLE FILE at startup, taking every caller
            # with it. Emitting valid JSON from Python removes that class.
            f.write(f"matrix={json.dumps(selected)}\n")

    unmeasured = sum(1 for r in results if r["state"] == "unmeasured")
    print(f"\n{len(results)} target(s) with a drift declaration; "
          f"{len(drifted)} drifted, {unmeasured} never measured, "
          f"{unknown} unreadable, {misdeclared} with an unimplemented mode")
    # 2, the same status an unreadable index returns: the workflow treats it
    # as "warn and carry on with the targets that DID answer" rather than
    # aborting the run, which is what keeps one bad declaration from
    # stopping every other target from being measured.
    return 2 if (unknown or misdeclared) else 0


if __name__ == "__main__":
    sys.exit(main())
