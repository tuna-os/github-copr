#!/usr/bin/env python3
"""Import Fedora dist-git RPM packaging into src/hummingbird.

Only packaging inputs are copied (specs, patches, source declarations and
auxiliary build files); the dist-git repository itself is never nested in this
repository.  The result is reviewable and can be built by build-chain.sh.

Two drivers:

  * the desktop catalog's `fedora_distgit:` sources (the original behaviour), and
  * a build-order manifest's `distgit:` keys, which is how the measured
    Hummingbird desktop graph is materialised — 599 of its 670 packages are
    unmodified Fedora Rawhide packaging and are imported rather than vendored.

Hummingbird's own RPM project (gitlab.com/redhat/hummingbird, ci/dist_git.py)
works the same way: >95% of its packages are auto-imported from Fedora dist-git,
tracked in a JSON state file, and carry a Release bumped by 0.1 so a downstream
rebuild sorts above the pristine Fedora build without colliding with it.  This
script mirrors that: --state records the dist-git commit each package came
from, and --release-bump applies the 0.1 convention.

Per Hummingbird convention no %changelog entry is added for the downstream
change; the commit message carries it.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import pathlib
import random
import re
import shutil
import subprocess
import tempfile
import threading
import time

import yaml

RELEASE = re.compile(r"^(Release:\s*)(\d+)(%\{\?dist\}.*)$", re.MULTILINE)

# src.fedoraproject.org throttles concurrent clones: with --jobs in flight it
# answers some of them with HTTP 503 or drops the connection outright ("fatal:
# the remote end hung up unexpectedly"), and it is a different subset of
# packages every time.  Run 31266178578 lost 17 of 24 clones that way and its
# rerun lost 13 of the same 24, with only three packages failing in both.  One
# attempt per package therefore turns a server-side hiccup into a failed
# import, so each clone is retried.
CLONE_ATTEMPTS = 6

# Retrying on a per-package schedule is not enough on its own: the server does
# not throttle one clone, it throttles the client, so the whole batch is
# refused at once and independent retries land back inside the same window and
# add to the load that caused it.  Run 31270801603 lost 20 of 66 imports that
# way, with four attempts each already in place.  So the backoff is shared: the
# first throttled clone parks every worker, and each fresh wave of throttling
# doubles the pause.
COOLDOWN_BASE = 5.0
COOLDOWN_CAP = 60.0

# ...unless the server is telling us the thing does not exist, which no amount
# of waiting fixes: a package absent from dist-git, or present without the
# requested branch, is a manifest bug and should surface on the first attempt.
CLONE_FATAL = re.compile(
    r"Remote branch .* not found|repository .* not found|error: 40[34]",
    re.IGNORECASE,
)


class Throttle:
    """A cooldown shared by every clone worker.

    `penalise()` is called by whichever worker the server refused; it parks
    *all* of them until the cooldown expires, so a throttled batch retries as
    one quiet pause instead of as N independent retries that keep the client
    over the limit.  Repeated waves back off further, up to `cap`.
    """

    def __init__(
        self,
        base: float = COOLDOWN_BASE,
        cap: float = COOLDOWN_CAP,
        clock=time.monotonic,
        sleep=time.sleep,
    ) -> None:
        self._lock = threading.Lock()
        self._clock = clock
        self._sleep = sleep
        self._cap = cap
        self._delay = base
        self._until = 0.0

    def wait(self) -> None:
        with self._lock:
            remaining = self._until - self._clock()
        if remaining > 0:
            # Jittered, so the clones parked together do not all resume in the
            # same instant and get throttled together again.
            self._sleep(remaining + random.uniform(0, 2))

    def penalise(self) -> None:
        with self._lock:
            now = self._clock()
            if now < self._until:
                # Already cooling down; this is another casualty of the same
                # wave, not a sign that the wait should be longer still.
                return
            self._until = now + self._delay
            self._delay = min(self._delay * 2, self._cap)


def catalog_packages(catalog: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    data = yaml.safe_load(catalog.read_text())
    result: list[tuple[str, pathlib.Path]] = []
    seen: set[str] = set()
    for desktop in data["desktops"].values():
        for source in desktop["sources"]:
            package = source.get("fedora_distgit")
            if package and package not in seen:
                seen.add(package)
                result.append((package, pathlib.Path("src/hummingbird") / package))
    return result


def build_order_packages(
    manifest: pathlib.Path, tiers: list[str] | None = None
) -> list[tuple[str, pathlib.Path]]:
    data = yaml.safe_load(manifest.read_text())
    known = {tier["name"] for tier in data.get("tiers", [])}
    if tiers:
        unknown = sorted(set(tiers) - known)
        if unknown:
            raise SystemExit(f"no such tier(s) in {manifest}: {unknown}")
    result: list[tuple[str, pathlib.Path]] = []
    seen: set[str] = set()
    for tier in data.get("tiers", []):
        if tiers and tier["name"] not in tiers:
            continue
        for package in tier.get("packages", []):
            name = package.get("distgit")
            if name and name not in seen:
                seen.add(name)
                result.append((name, pathlib.Path(package["path"])))
    return result


def bump_release(specdir: pathlib.Path) -> str | None:
    """Release: 3%{?dist} -> Release: 3.1%{?dist}.

    Sorts above the pristine Fedora build (3.1 > 3) so a rebuilt package is
    never shadowed by a Fedora one that leaks into the same transaction, and is
    identifiable at a glance in `rpm -qa`.
    """
    for spec in sorted(specdir.glob("*.spec")):
        text = spec.read_text()
        bumped, count = RELEASE.subn(r"\g<1>\g<2>.1\g<3>", text, count=1)
        if count:
            spec.write_text(bumped)
            return spec.name
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=pathlib.Path, nargs="?")
    parser.add_argument(
        "--build-order", type=pathlib.Path,
        help="Import every `distgit:` entry of a build-order manifest.",
    )
    parser.add_argument(
        "--tier", action="append", dest="tiers",
        help="Restrict --build-order to these tiers. Repeatable. Importing "
             "the whole manifest is 599 dist-git clones; a tiered run needs "
             "only its own.",
    )
    parser.add_argument("--branch", default="rawhide")
    parser.add_argument("--package", action="append", dest="packages")
    parser.add_argument("--dest", type=pathlib.Path, default=pathlib.Path("src/hummingbird"))
    parser.add_argument(
        "--state", type=pathlib.Path,
        help="JSON file recording the dist-git commit each package came from.",
    )
    parser.add_argument(
        "--release-bump", action="store_true",
        help="Apply Hummingbird's +0.1 Release convention to the imported spec.",
    )
    parser.add_argument(
        "--jobs", type=int, default=4,
        help="Parallel dist-git clones. The clones are network-bound and "
             "independent; the copy and the state file stay serial so the "
             "result does not depend on completion order.",
    )
    parser.add_argument(
        "--clone-cooldown", type=float, default=COOLDOWN_BASE, metavar="SECONDS",
        help="First pause taken by every worker once src.fedoraproject.org "
             "starts refusing clones; it doubles per wave. 0 disables the "
             "wait, which is only useful against a stub server.",
    )
    args = parser.parse_args()

    if args.packages:
        wanted = [(name, args.dest / name) for name in args.packages]
    elif args.build_order:
        wanted = build_order_packages(args.build_order, args.tiers)
    elif args.catalog:
        wanted = catalog_packages(args.catalog)
    else:
        parser.error("pass a catalog, --build-order or --package")

    state: dict[str, dict] = {}
    if args.state and args.state.exists():
        state = json.loads(args.state.read_text())

    imported = skipped = failed = 0
    with tempfile.TemporaryDirectory(prefix="tunaos-distgit-") as temp:
        tempdir = pathlib.Path(temp)
        pending = []
        for package, relative in wanted:
            target = relative if relative.is_absolute() else pathlib.Path.cwd() / relative
            if target.exists():
                print(f"Skipping {package}: {target} already exists")
                skipped += 1
                continue
            pending.append((package, relative, target))

        throttle = Throttle(base=args.clone_cooldown)

        def clone_one(item):
            package, _, _ = item
            checkout = tempdir / package
            url = f"https://src.fedoraproject.org/rpms/{package}.git"
            for attempt in range(1, CLONE_ATTEMPTS + 1):
                # Nothing is asked of the server while it is refusing clones,
                # including this worker's first attempt: joining a throttled
                # wave only prolongs it.
                throttle.wait()
                # git leaves nothing behind when it fails this way, but a
                # half-written checkout would make the retry fail on "already
                # exists" rather than on the network.
                shutil.rmtree(checkout, ignore_errors=True)
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", "--branch", args.branch, url, str(checkout)],
                    capture_output=True, text=True,
                )
                if result.returncode == 0 or CLONE_FATAL.search(result.stderr):
                    break
                throttle.penalise()
            return item, result, attempt

        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            outcomes = list(pool.map(clone_one, pending))

        for (package, relative, target), clone, attempts in outcomes:
            checkout = tempdir / package
            if clone.returncode != 0:
                tail = clone.stderr.strip().splitlines()[-1:] or ["clone failed"]
                tries = "" if attempts == 1 else f" after {attempts} attempts"
                print(f"FAILED {package}{tries}: {tail[0]}")
                failed += 1
                continue
            commit = subprocess.run(
                ["git", "-C", str(checkout), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            target.mkdir(parents=True)
            for source in checkout.iterdir():
                if source.name == ".git":
                    continue
                if source.is_dir():
                    shutil.copytree(source, target / source.name)
                else:
                    shutil.copy2(source, target / source.name)
            spec = bump_release(target) if args.release_bump else None
            state[package] = {
                "branch": args.branch,
                "commit": commit,
                "path": str(relative),
                "release_bumped": bool(spec),
            }
            print(f"Imported {package} from {args.branch} at {commit[:12]}")
            imported += 1

    if args.state:
        args.state.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")

    print(f"imported={imported} skipped={skipped} failed={failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
