#!/usr/bin/env python3
"""Resume a build-chain cell from what a previous attempt already built.

## The problem

A build-chain cell has `timeout-minutes: 360`. The GNOME cells build ~55
packages and have hit that ceiling (#480). When they do, the job is reported
as CANCELLED, and everything it built -- up to six hours of mock runs -- is
discarded. The next dispatch starts again at tier 0 and hits the same wall in
the same place. That is not a slow build; it is a build that cannot finish.

## Why the existing caches do not cover it

Two mechanisms already store a cell's output and neither survives a timeout:

  * The action cache (`Save validated output`) is written only after the
    build succeeds. A timed-out attempt never reaches it.
  * The failure artifact upload is `if: failure()`, and a `timeout-minutes`
    overrun CANCELS the job rather than failing it, so that step is skipped
    too. Nothing at all is kept.

The action cache is also the wrong tool here even if it were reachable: it is
capped at 10GB per repository with LRU eviction, and the largest cells ran to
1.35GB (#472). Adding a second multi-hundred-MB entry per long cell would
evict the authoritative entries for the ~294 short ones. Workflow artifacts
are separately stored and not subject to that cap, so partial output goes
there.

## Why resuming is safe

build-chain.sh already skips a package whose exact NVR is present in the
local repo (`check_package_exists`). Restoring a previous attempt's RPMs into
the local repo therefore produces exactly the state that attempt was in -- no
new code path in the builder, and no new failure mode.

What makes it CORRECT rather than merely convenient is the action key. The
native key is derived from the manifest, every source path, the image digest
and the source epoch, so it changes whenever anything that could change a
built RPM changes. A partial whose recorded key differs from this cell's is
discarded, not merged. Same key means the RPMs a previous attempt built are
what this attempt would build.

And a resumed run is validated no differently from a fresh one: it still runs
the lint, the install/smoke verify, and writes its ActionResult over whatever
ends up in artifacts/. A partial can shorten a run; it cannot let one skip a
gate.

## Failure is not fatal

Every failure here -- no prior artifact, an expired one, a bad zip, a key
mismatch, a rate-limited API -- means "build from scratch", which is the
behaviour that exists today. This script logs and exits 0 on all of them. A
resume that does not work must never be the reason a cell fails.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import shutil
import sys
import urllib.error
import urllib.request
import zipfile

API = "https://api.github.com"
# How far down the newest-first list to look for a partial that
# actually carries packages. More than a couple of consecutive
# empty uploads means something other than a blip is wrong.
MAX_CANDIDATES = 5
KEY_FILE = "action-key.txt"


def log(message: str) -> None:
    print(f"[resume] {message}", flush=True)


def api_get(url: str, token: str):
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    return json.loads(payload)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_artifact(url: str, token: str) -> bytes:
    """Fetch the artifact zip, following GitHub's redirect BY HAND.

    The archive endpoint answers 302 with a pre-signed blob-storage URL in
    Location. urllib's default redirect handler replays every original header
    against the new host -- including Authorization -- and Azure answers a
    GitHub bearer token with HTTP 401 ("Server failed to authenticate the
    request"). That 401 made every resume fall back to building from scratch,
    which put the hummingbird cells right back on the 6-hour wall this script
    exists to remove (#480). So: authenticate the GitHub hop, then fetch the
    pre-signed Location with no Authorization header at all.
    """
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=120) as response:
            # GitHub documents a redirect, but a direct 200 is fine too.
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code not in (301, 302, 303, 307, 308):
            raise
        location = error.headers.get("Location")
        if not location:
            raise
    # A 445 MB zip at ~10 MB/s wants far more than the API timeout.
    with urllib.request.urlopen(location, timeout=1800) as response:
        return response.read()


def unexpired_partials(repository: str, name: str, token: str) -> list[dict]:
    """Every unexpired artifact with this exact name, newest first.

    The artifacts endpoint filters by name across the whole repository and
    returns newest first, so this is one request rather than a walk over runs.

    ACROSS THE WHOLE REPOSITORY is the property that makes this work where
    the action cache cannot. GitHub scopes caches by ref: a run on
    `refs/pull/N/merge` writes entries only that PR can read, and a merge
    QUEUE run lives on `refs/heads/gh-readonly-queue/...`, which sees main's
    caches and never the PR's. The artifacts API has no such scoping, so an
    artifact is reachable from any run in the repository.

    Newest FIRST, deliberately not newest-only: see the walk in main().
    """
    url = f"{API}/repos/{repository}/actions/artifacts?name={name}&per_page=30"
    listing = api_get(url, token)
    return [a for a in (listing.get("artifacts") or []) if not a.get("expired")]


def reusable_outputs(repository: str, names: list[str], token: str) -> list[dict]:
    """Candidates from every name that can carry this cell's packages.

    Two artifacts can: the `-partial` an interrupted attempt banks, and the
    plain `<cell-id>` a SUCCESSFUL one uploads. Both contain `artifacts/`
    and, once the success upload carries it, the key that says which inputs
    produced them -- and the key is the whole basis on which either is
    accepted, so where the RPMs came from does not matter. A complete
    attempt is simply a better partial: more packages, same guarantee.

    Reading the success artifact is what lets a merge-queue run reuse the
    evidence its own PR already produced. The PR's gate builds the cell and
    stores it in a ref-scoped cache the queue commit cannot read, so the
    queue rebuilt every `src/`-touching PR from zero -- hours of work
    against a merge-queue CI timeout of about an hour, which evicted PR #567
    with CI_TIMEOUT on every attempt and made such PRs unmergeable no matter
    how green they were.

    Merged newest-first across names, because "newest" is the useful
    ordering and which name it came from is not.
    """
    found: list[dict] = []
    for name in names:
        for artifact in unexpired_partials(repository, name, token):
            artifact = dict(artifact)
            artifact["_source_name"] = name
            found.append(artifact)
    found.sort(key=lambda a: a.get("created_at") or "", reverse=True)
    return found


def extract(blob: bytes, destination: pathlib.Path) -> tuple[str | None, int]:
    """Unpack artifacts/ and the recorded action key, and nothing else.

    The partial upload carries the whole cell directory because that is what a
    person debugging a failure wants. Only two parts of it are safe to reuse:
    the finished RPMs, and the key that says which inputs produced them. The
    build tree is deliberately NOT restored -- a mock buildroot interrupted
    mid-package is not a resumable state, and dropping it also keeps the
    restore small.
    """
    recovered = 0
    key = None
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = entry.filename
            if name == KEY_FILE:
                key = archive.read(entry).decode("utf-8", "replace").strip()
                continue
            if not name.startswith("artifacts/"):
                continue
            # Refuse to write outside the destination. The zip comes from this
            # repository's own runs, but a path check costs one line and the
            # alternative is an arbitrary-write primitive.
            target = (destination / name).resolve()
            if not str(target).startswith(str(destination.resolve()) + os.sep):
                log(f"skipping entry outside the cell directory: {name}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, open(target, "wb") as sink:
                shutil.copyfileobj(source, sink)
            recovered += 1
    return key, recovered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell-id", required=True)
    parser.add_argument("--action-key", required=True)
    parser.add_argument("--out-dir", required=True,
                        help="the cell directory, e.g. .factory/<id>")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token or not args.repository:
        log("no token or repository in the environment; building from scratch")
        return 0

    names = [f"{args.cell_id}-partial", args.cell_id]
    try:
        candidates = reusable_outputs(args.repository, names, token)
    except (urllib.error.URLError, ValueError, OSError) as error:
        log(f"could not list artifacts ({error}); building from scratch")
        return 0
    if not candidates:
        log(f"no unexpired {' or '.join(f'`{n}`' for n in names)} artifact; "
            "building from scratch")
        return 0

    # Extract somewhere disposable first. A key mismatch must leave the cell
    # directory exactly as it was, not half-populated with another key's RPMs.
    out = pathlib.Path(args.out_dir)
    staging = out.parent / f".{out.name}-partial-staging"
    source = None
    recovered = 0
    # Newest first, but NOT newest-only. A cell that dies before it builds
    # anything still uploads a partial, and that empty artifact is NEWER
    # than the one the previous run banked: on 2026-08-25 an upstream mirror
    # served a bad repomd.xml, the gnome51 x86_64 cell died at its first
    # buildroot, and its 6KB partial shadowed the 247MB one behind it --
    # discarding hours of banked packages, the one thing resume exists to
    # prevent. So walk down the list until one actually carries packages.
    # Downloading a useless candidate is cheap precisely because it is empty.
    for artifact in candidates[:MAX_CANDIDATES]:
        log(f"found `{artifact.get('_source_name')}` from "
            f"{artifact.get('created_at')} "
            f"({artifact.get('size_in_bytes', 0) / 1e6:.0f} MB)")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        try:
            blob = download_artifact(artifact["archive_download_url"], token)
            key, recovered = extract(blob, staging)
        except (urllib.error.URLError, OSError, zipfile.BadZipFile) as error:
            log(f"  could not use it ({error}); trying an older one")
            continue
        if key != args.action_key:
            log(f"  action key differs (partial {key or 'absent'}, this cell "
                f"{args.action_key}); trying an older one")
            continue
        candidate = staging / "artifacts"
        if not candidate.is_dir() or not any(candidate.glob("*.rpm")):
            log("  it carries no packages; trying an older one")
            continue
        source = candidate
        break

    if source is None:
        log("no unexpired artifact carries usable packages with a "
            "matching key; building from scratch")
        shutil.rmtree(staging, ignore_errors=True)
        return 0

    destination = out / "artifacts"
    destination.mkdir(parents=True, exist_ok=True)
    packages = 0
    # Files only, and that is what drops the previous attempt's repodata/:
    # build-chain.sh keeps a FLAT local repo (`cp "$rpm" "${LOCAL_REPO}/"`),
    # so every package is a file at the top level and the only subdirectory
    # is the index. Leaving it behind is correct -- createrepo_c regenerates
    # it before the first mock run, and a stale index naming packages that
    # did not come across would be worse than none.
    for path in sorted(source.iterdir()):
        if not path.is_file():
            continue
        shutil.move(str(path), str(destination / path.name))
        packages += 1
    shutil.rmtree(staging, ignore_errors=True)

    log(f"resumed with {packages} packages from the previous attempt "
        f"({recovered} entries in the partial)")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"resumed `{args.cell_id}` with **{packages}** "
                         f"packages from a previous attempt\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
