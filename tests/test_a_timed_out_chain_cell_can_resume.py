"""A six-hour cell that runs out of clock must not lose six hours of work.

`timeout-minutes: 360` is a real ceiling for the GNOME cells, which build ~55
packages (#480). Before this, hitting it cost everything:

  * The action cache is written by `Save validated output`, which runs only
    after a successful build. A timed-out attempt never reaches it.
  * The debugging artifact upload was `if: failure()`, and a job torn down
    for exceeding `timeout-minutes` is CANCELLED, not failed -- so that step
    was skipped too.

Nothing at all survived, and the re-dispatch restarted at tier 0 and stopped
in the same place. A build that cannot finish is not a slow build.

The recovery has three parts and each fails silently if it is wrong, which is
why all three are pinned here:

1. The partial must actually be uploaded when the clock runs out.
2. It must be SMALL. A cancelled job gets a short grace period; an upload of
   the full cell directory (95.4% build tree on the cell #472 measured) does
   not finish inside it, and an upload that does not finish recovers nothing.
3. It must only be reused when the inputs match. The action key is what makes
   a resumed build equal to a fresh one rather than a mixture of two.
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import zipfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CELL = ROOT / ".github" / "workflows" / "package-factory-cell.yml"
SCRIPT = ROOT / "scripts" / "restore-partial-chain-output.py"


def steps() -> list[dict]:
    return yaml.safe_load(CELL.read_text())["jobs"]["build"]["steps"]


def step_named(fragment: str) -> dict:
    for step in steps():
        if fragment in (step.get("name") or "") or fragment in (step.get("uses") or ""):
            return step
    raise AssertionError(f"no step matching {fragment!r}")


def load_module():
    spec = importlib.util.spec_from_file_location("restore_partial", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def partial_upload() -> dict:
    for step in steps():
        with_ = step.get("with") or {}
        if "-partial" in str(with_.get("name", "")):
            return step
    raise AssertionError("no step uploads a `-partial` artifact")


def test_the_partial_is_uploaded_when_the_clock_runs_out():
    """`always()`, not `failure()`.

    `failure()` was the bug: a job torn down for exceeding `timeout-minutes`
    is reported as cancelled, so the upload never ran. `always()` is the one
    condition GitHub documents as still running when a job is torn down.
    """
    condition = partial_upload()["if"]
    assert "always()" in condition, (
        "the partial upload must be always(); a timed-out job is not a failure() "
        "and that is the case this exists for"
    )
    # And not on a clean run, where the action cache already holds the output.
    assert "steps.build.outcome != 'success'" in condition


def test_the_partial_carries_only_what_a_resume_reads():
    """A cancelled job has a short grace period to finish its steps.

    The debugging upload takes the whole cell directory, and the build tree
    dwarfs the output -- 95.4% of the bytes on the cell measured in #472. An
    upload that does not finish inside the grace window recovers nothing, so
    the partial must be the packages and the key and nothing else.
    """
    paths = [line.strip() for line in partial_upload()["with"]["path"].splitlines()
             if line.strip()]
    assert any(path.endswith("artifacts/") for path in paths)
    assert any(path.endswith("action-key.txt") for path in paths)
    for path in paths:
        assert not path.rstrip("/").endswith("${{ matrix.id }}"), (
            "the partial must not be the whole cell directory: it has to upload "
            f"inside a cancellation grace window ({path})"
        )


def test_the_partial_cannot_be_confused_with_the_success_artifact():
    """The resume queries the artifacts API by exact name.

    If the partial shared `${{ matrix.id }}` with the success upload, that
    query could return a validated deliverable and a half-finished attempt
    interchangeably.
    """
    names = {(step.get("with") or {}).get("name") for step in steps()}
    assert "${{ matrix.id }}-partial" in names
    assert "${{ matrix.id }}" in names
    module = load_module()
    assert module.unexpired_partials.__doc__, (
        "the lookup is by exact name; say so")


def test_the_action_key_is_written_where_the_partial_can_carry_it():
    """The key lives in the cell directory, not only in the step output.

    A step output does not survive the job. Matching a partial to its inputs
    needs the key to be a file inside what gets uploaded.
    """
    identity = step_named("Resolve immutable inputs and action key")
    assert "action-key.txt" in identity["run"]


def test_a_partial_from_different_inputs_is_discarded_not_merged(tmp_path):
    """This is the property that makes a resumed build equal to a fresh one.

    RPMs from a different action key came from a different manifest, spec,
    image or epoch. Merging them into the local repo would make build-chain's
    NVR skip fire for packages this cell would have built differently -- and
    the result would pass every downstream gate, because each individual RPM
    is well-formed. It would just not be the thing the inputs describe.
    """
    module = load_module()
    blob = tmp_path / "partial.zip"
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("action-key.txt", "aaaa1111\n")
        archive.writestr("artifacts/glib2-2.87.3-1.el10.x86_64.rpm", "not really an rpm")

    staging = tmp_path / "staging"
    staging.mkdir()
    key, recovered = module.extract(blob.read_bytes(), staging)
    assert key == "aaaa1111"
    assert recovered == 1
    # The caller compares before moving anything into the cell directory.
    source = SCRIPT.read_text()
    mismatch = source.index("action key differs")
    move = source.index("shutil.move")
    assert mismatch < move, (
        "the key comparison must happen before any file is moved into the cell "
        "directory, or a mismatch leaves it half-populated"
    )


def test_the_build_tree_is_never_restored(tmp_path):
    """Only artifacts/ comes back.

    A mock buildroot interrupted mid-package is not a resumable state, and
    build-chain.sh has no notion of continuing one. Restoring it would carry
    a half-written chroot into a fresh run for no benefit.
    """
    module = load_module()
    blob = tmp_path / "partial.zip"
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("action-key.txt", "k")
        archive.writestr("artifacts/pango-1.0-1.el10.x86_64.rpm", "rpm")
        archive.writestr("rpm/rpmbuild/BUILD/half-written-tree/config.log", "junk")
    staging = tmp_path / "staging"
    staging.mkdir()
    module.extract(blob.read_bytes(), staging)
    assert (staging / "artifacts").is_dir()
    assert not (staging / "rpm").exists()


def test_a_traversal_entry_cannot_write_outside_the_cell(tmp_path):
    """A path check costs one line; the alternative is an arbitrary write."""
    module = load_module()
    blob = tmp_path / "partial.zip"
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("artifacts/../../escaped.rpm", "no")
    staging = tmp_path / "staging"
    staging.mkdir()
    module.extract(blob.read_bytes(), staging)
    assert not (tmp_path.parent / "escaped.rpm").exists()
    assert not (tmp_path / "escaped.rpm").exists()


def test_a_resume_that_cannot_work_is_never_a_build_failure():
    """No prior artifact, an expired one, a bad zip, a rate-limited API.

    Every one of those means "build from scratch", which is exactly today's
    behaviour. A recovery mechanism that can turn a working build red is
    worse than no recovery mechanism.
    """
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--cell-id", "gnome51-el10-x86_64",
         "--action-key", "deadbeef", "--out-dir", "/nonexistent/cell"],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin"},  # no GITHUB_TOKEN, no GITHUB_REPOSITORY
    )
    assert completed.returncode == 0, completed.stderr
    assert "building from scratch" in completed.stdout


def test_the_resume_only_runs_for_the_engine_that_has_progress_to_resume():
    """A tideforge cell builds one package. There is no partial state."""
    resume = step_named("Resume from a previous attempt")
    assert "matrix.engine == 'build-chain'" in resume["if"]
    assert "steps.verdict.outputs.hit != 'true'" in resume["if"]
    assert "matrix.engine == 'build-chain'" in partial_upload()["if"]


def test_the_resume_runs_before_the_build():
    names = [step.get("name") or step.get("uses") or "" for step in steps()]
    resume = next(i for i, n in enumerate(names) if "Resume from a previous" in n)
    build = next(i for i, n in enumerate(names) if n == "Build on an exact miss")
    assert resume < build


def test_the_job_may_read_its_own_workflow_artifacts():
    """`actions: read`. Without it the API listing 404s and every resume
    silently degrades to a full rebuild -- the exact failure this fixes,
    reintroduced as a permissions omission."""
    permissions = yaml.safe_load(CELL.read_text())["permissions"]
    assert permissions.get("actions") == "read"


def _fake_api(module, listing, blob):
    """Stand in for the artifacts API so the happy path is exercised, not read."""
    module.api_get = lambda url, token: listing
    module.download_artifact = lambda url, token: blob


def test_a_matching_partial_lands_in_the_local_repo(tmp_path, monkeypatch):
    """The whole point, end to end.

    build-chain.sh is given `--local-repo <cell>/artifacts` and skips any
    package whose exact NVR is already a file there. Landing the previous
    attempt's RPMs in that directory is therefore the entire resume: no new
    code path in the builder, and the state it wakes up in is the state the
    previous attempt was in.
    """
    module = load_module()
    blob = tmp_path / "partial.zip"
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("action-key.txt", "matching-key\n")
        archive.writestr("artifacts/glib2-2.88.0-2.el10.x86_64.rpm", "rpm")
        archive.writestr("artifacts/pango-1.56.4-1.el10.x86_64.rpm", "rpm")
        # Regenerated by createrepo_c on the next run; must not be carried over.
        archive.writestr("artifacts/repodata/repomd.xml", "<stale/>")
    _fake_api(module, {"artifacts": [{
        "expired": False, "created_at": "2026-08-23T14:52:00Z",
        "size_in_bytes": 1234, "archive_download_url": "https://example.invalid/z",
    }]}, blob.read_bytes())

    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "tuna-os/tunaos-packages")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    out = tmp_path / "cell"
    monkeypatch.setattr(sys, "argv", [
        "restore", "--cell-id", "gnome51-el10-x86_64",
        "--action-key", "matching-key", "--out-dir", str(out)])
    assert module.main() == 0

    landed = sorted(p.name for p in (out / "artifacts").iterdir())
    assert landed == ["glib2-2.88.0-2.el10.x86_64.rpm", "pango-1.56.4-1.el10.x86_64.rpm"]
    assert not (out / "artifacts" / "repodata").exists(), (
        "a stale repodata index must not outlive the attempt that wrote it: "
        "createrepo_c regenerates it, and an index naming packages that did "
        "not come across is worse than no index"
    )
    assert not list(tmp_path.glob(".*-partial-staging")), "staging must be cleaned up"


def test_a_mismatched_partial_leaves_the_cell_directory_untouched(tmp_path, monkeypatch):
    """The consequence of getting this wrong is not a red build.

    Every RPM in a partial is well-formed, so a mixture of two input sets
    passes lint, install, smoke and the ActionResult hash alike. It is simply
    not the thing the manifest describes. Nothing downstream can catch it,
    which is why the check is here.
    """
    module = load_module()
    blob = tmp_path / "partial.zip"
    with zipfile.ZipFile(blob, "w") as archive:
        archive.writestr("action-key.txt", "an-older-key\n")
        archive.writestr("artifacts/glib2-2.87.3-1.el10.x86_64.rpm", "rpm")
    _fake_api(module, {"artifacts": [{
        "expired": False, "created_at": "2026-08-01T00:00:00Z",
        "size_in_bytes": 1, "archive_download_url": "https://example.invalid/z",
    }]}, blob.read_bytes())

    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "tuna-os/tunaos-packages")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    out = tmp_path / "cell"
    monkeypatch.setattr(sys, "argv", [
        "restore", "--cell-id", "gnome51-el10-x86_64",
        "--action-key", "the-current-key", "--out-dir", str(out)])
    assert module.main() == 0
    assert not out.exists(), "a mismatched partial must land nothing at all"


def test_the_download_does_not_leak_the_token_through_the_redirect(tmp_path):
    """The bug that made every resume a no-op (#480).

    GitHub's archive endpoint answers 302 with a pre-signed blob-storage URL.
    urllib's default redirect handler replays the original headers -- with
    Authorization -- against the new host, and Azure answers a GitHub bearer
    token with HTTP 401. The nightly logged exactly that ("could not download
    it (HTTP Error 401 ...); building from scratch"), rebuilt six hours of
    work, and timed out in the same place again.

    This server refuses the redirected request if Authorization is present,
    which is Azure's observable behaviour. It also proves the token IS sent
    on the first hop, where GitHub requires it.
    """
    import http.server
    import threading

    payload = tmp_path / "partial.zip"
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("action-key.txt", "k\n")
        archive.writestr("artifacts/glib2-2.88.0-2.el10.x86_64.rpm", "rpm")
    blob = payload.read_bytes()
    seen = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/artifact/zip":
                seen["api_auth"] = self.headers.get("Authorization")
                self.send_response(302)
                self.send_header(
                    "Location", f"http://127.0.0.1:{self.server.server_port}/blob")
                self.end_headers()
            elif self.path == "/blob":
                seen["blob_auth"] = self.headers.get("Authorization")
                if self.headers.get("Authorization"):
                    self.send_response(401)  # what Azure does with a GitHub token
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(blob)))
                self.end_headers()
                self.wfile.write(blob)

        def log_message(self, *_):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        module = load_module()
        url = f"http://127.0.0.1:{server.server_port}/api/artifact/zip"
        fetched = module.download_artifact(url, "ghs_secret")
    finally:
        server.shutdown()
        thread.join()

    assert fetched == blob
    assert seen["api_auth"] == "Bearer ghs_secret", (
        "the GitHub hop must be authenticated -- artifact downloads 404 without it"
    )
    assert seen["blob_auth"] is None, (
        "the Authorization header must not follow the redirect: the blob host "
        "answers a GitHub token with 401 and the resume silently degrades to "
        "a full rebuild"
    )


def test_an_expired_artifact_is_skipped(tmp_path, monkeypatch):
    """Artifacts expire; the API still lists them, with no downloadable zip."""
    module = load_module()
    _fake_api(module, {"artifacts": [
        {"expired": True, "created_at": "2026-05-01T00:00:00Z",
         "archive_download_url": "https://example.invalid/gone"},
    ]}, b"")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "tuna-os/tunaos-packages")
    assert module.unexpired_partials(
        "tuna-os/tunaos-packages", "x-partial", "t") == []


def _fake_api_by_url(module, listing, blobs):
    """Like _fake_api, but each candidate download returns its own bytes."""
    module.api_get = lambda url, token: listing
    module.download_artifact = lambda url, token: blobs[url]


def test_an_empty_newer_partial_does_not_shadow_the_banked_one(
        tmp_path, monkeypatch):
    """The 2026-08-25 loss: newest is not the same as usable.

    An upstream mirror served a bad repomd.xml, the gnome51 x86_64 cell died
    at its first buildroot having built nothing, and still uploaded a
    partial. That 6KB artifact was NEWER than the 247MB one banked by the
    run before it, so the next resume would have restored nothing and thrown
    away hours of packages -- the exact loss resume exists to prevent.
    """
    module = load_module()
    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("action-key.txt", "matching-key\n")

    banked = tmp_path / "banked.zip"
    with zipfile.ZipFile(banked, "w") as archive:
        archive.writestr("action-key.txt", "matching-key\n")
        archive.writestr("artifacts/glib2-2.89.4-2.el10.x86_64.rpm", "rpm")
        archive.writestr("artifacts/pango-1.57.0-1.el10.x86_64.rpm", "rpm")

    _fake_api_by_url(module, {"artifacts": [
        {"expired": False, "created_at": "2026-08-25T21:52:27Z",
         "size_in_bytes": 6028,
         "archive_download_url": "https://example.invalid/empty"},
        {"expired": False, "created_at": "2026-08-25T21:26:09Z",
         "size_in_bytes": 247522035,
         "archive_download_url": "https://example.invalid/banked"},
    ]}, {"https://example.invalid/empty": empty.read_bytes(),
         "https://example.invalid/banked": banked.read_bytes()})

    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "tuna-os/tunaos-packages")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    out = tmp_path / "cell"
    monkeypatch.setattr(sys, "argv", [
        "restore", "--cell-id", "gnome51-el10-x86_64",
        "--action-key", "matching-key", "--out-dir", str(out)])
    assert module.main() == 0

    landed = sorted(p.name for p in (out / "artifacts").iterdir())
    assert landed == ["glib2-2.89.4-2.el10.x86_64.rpm",
                      "pango-1.57.0-1.el10.x86_64.rpm"], (
        "the empty newer partial shadowed the banked one; a run that built "
        "nothing must not be able to discard a run that built everything")


def test_the_walk_stops_rather_than_restoring_another_cells_key(
        tmp_path, monkeypatch):
    """Walking past an empty partial must not relax the key check.

    The key is what makes a restore sound: it says these RPMs came from
    exactly these inputs. Skipping empties is a search for a USABLE partial,
    not a search for any partial.
    """
    module = load_module()
    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("action-key.txt", "matching-key\n")
    foreign = tmp_path / "foreign.zip"
    with zipfile.ZipFile(foreign, "w") as archive:
        archive.writestr("action-key.txt", "some-other-key\n")
        archive.writestr("artifacts/glib2-2.88.0-4.el10.x86_64.rpm", "rpm")

    _fake_api_by_url(module, {"artifacts": [
        {"expired": False, "created_at": "2026-08-25T21:52:27Z",
         "size_in_bytes": 6028,
         "archive_download_url": "https://example.invalid/empty"},
        {"expired": False, "created_at": "2026-08-25T20:00:00Z",
         "size_in_bytes": 999,
         "archive_download_url": "https://example.invalid/foreign"},
    ]}, {"https://example.invalid/empty": empty.read_bytes(),
         "https://example.invalid/foreign": foreign.read_bytes()})

    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "tuna-os/tunaos-packages")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    out = tmp_path / "cell"
    monkeypatch.setattr(sys, "argv", [
        "restore", "--cell-id", "gnome51-el10-x86_64",
        "--action-key", "matching-key", "--out-dir", str(out)])
    assert module.main() == 0
    assert not (out / "artifacts").exists(), (
        "a partial built from different inputs was restored anyway")
    assert not list(tmp_path.glob(".*-partial-staging")), "staging left behind"
