"""A merge-queue run must not rebuild what the PR it is merging just built.

GitHub scopes the Actions cache by ref. A PR's gate runs on
`refs/pull/N/merge` and writes cache entries only that PR can read; a merge
QUEUE run lives on `refs/heads/gh-readonly-queue/main/pr-N-<sha>`, which can
read main's caches and never the PR's. So a PR that changes `src/` has an
action key main has never built, the queue run finds nothing, and it rebuilds
the cells from zero.

That is not merely slow, it is disqualifying. Measured on 2026-08-28:

    merge-group run   touches src/   duration                  outcome
    pr-570            no             77 s                      merged
    pr-567            yes            63 min, still building    CI_TIMEOUT

The queue's CI timeout is about an hour and the gnome cells take hours, so
every `src/`-touching PR was evicted on every attempt no matter how green it
was on its own head. #545 and #567 both hit it.

The artifacts API has no ref scoping: an artifact is reachable from any run
in the repository. The resume path already fetches artifacts across runs and
accepts one only when its recorded action key matches this cell's -- so the
fix is to let it also see the artifact a SUCCESSFUL build uploads, and to
make that artifact carry the key it is judged by.

What keeps this honest is the key, not the name. Same key means the same
manifest slice, source digests, image digest and epoch, which is exactly the
basis on which cache hits and partial resumes are already accepted
everywhere else in this factory. A complete attempt is a better partial:
more packages, identical guarantee.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

yaml = pytest.importorskip("yaml")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "restore-partial-chain-output.py"
CELL = ROOT / ".github" / "workflows" / "package-factory-cell.yml"


def load_module():
    spec = importlib.util.spec_from_file_location("restore_partial", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cell_steps():
    data = yaml.safe_load(CELL.read_text(encoding="utf-8"))
    for job in data["jobs"].values():
        if job.get("steps"):
            return job["steps"]
    raise AssertionError("no job with steps in the cell workflow")


def success_upload():
    for step in cell_steps():
        if ("upload-artifact" in str(step.get("uses", ""))
                and str(step.get("if", "")).strip() == "success()"):
            return step
    raise AssertionError("no success-conditioned upload-artifact step")


# --- the restore must look at both names -------------------------------------

def test_restore_considers_the_success_artifact_not_only_the_partial():
    module = load_module()
    assert hasattr(module, "reusable_outputs"), (
        "the lookup that spans both artifact names is what makes a "
        "merge-queue run able to reuse its PR's build"
    )


def test_both_candidate_names_are_queried(monkeypatch):
    module = load_module()
    asked: list[str] = []

    def fake(repository, name, token):
        asked.append(name)
        return [{"created_at": f"2026-08-28T0{len(asked)}:00:00Z",
                 "size_in_bytes": 1}]

    monkeypatch.setattr(module, "unexpired_partials", fake)
    module.reusable_outputs("o/r", ["cell-partial", "cell"], "t")
    assert asked == ["cell-partial", "cell"], (
        "a run must see the interrupted attempt AND the validated one"
    )


def test_candidates_are_merged_newest_first(monkeypatch):
    """Which name it came from must not outrank how recent it is."""
    module = load_module()
    by_name = {
        "cell-partial": [{"created_at": "2026-08-01T00:00:00Z", "id": "old"}],
        "cell": [{"created_at": "2026-08-28T00:00:00Z", "id": "new"}],
    }
    monkeypatch.setattr(module, "unexpired_partials",
                        lambda repo, name, token: by_name[name])
    merged = module.reusable_outputs("o/r", ["cell-partial", "cell"], "t")
    assert [c["id"] for c in merged] == ["new", "old"]


def test_each_candidate_remembers_which_name_it_came_from(monkeypatch):
    """The log line that says what was restored has to be truthful."""
    module = load_module()
    monkeypatch.setattr(
        module, "unexpired_partials",
        lambda repo, name, token: [{"created_at": "2026-08-28T00:00:00Z"}],
    )
    merged = module.reusable_outputs("o/r", ["a-partial", "a"], "t")
    assert {c["_source_name"] for c in merged} == {"a-partial", "a"}


def test_the_ref_scoping_that_makes_this_necessary_is_written_down():
    doc = load_module().unexpired_partials.__doc__ or ""
    assert "scopes caches by ref" in doc or "ref-scoped" in doc or "scoping" in doc, (
        "the next reader must learn why the cache cannot serve this, or they "
        "will 'simplify' it back to a cache lookup"
    )


# --- the success artifact must carry the key it is judged by ------------------

def test_the_success_artifact_carries_its_action_key():
    paths = str(success_upload()["with"]["path"])
    assert "action-key.txt" in paths, (
        "restore reads the key from the zip and discards any candidate whose "
        "key is absent -- without this line the success artifact can never be "
        "reused, however recent it is"
    )


def test_the_success_artifact_still_carries_the_packages():
    paths = str(success_upload()["with"]["path"])
    assert "artifacts/" in paths, (
        "the RPMs are the thing being reused; the key alone restores nothing"
    )


def test_the_two_artifact_names_stay_distinct():
    """Querying both names is deliberate; COLLIDING them would not be.

    One name for both would make `overwrite: true` on the partial able to
    replace a validated deliverable.
    """
    names = {(s.get("with") or {}).get("name") for s in cell_steps()}
    assert "${{ matrix.base_id || matrix.id }}-partial" in names
    assert "${{ matrix.id }}" in names


def test_a_key_mismatch_still_discards_the_candidate():
    """The widened search must not widen what is ACCEPTED.

    Reuse is safe only because the key is checked; if that check ever
    softens, a merge-queue run could ship RPMs built from other inputs.
    """
    body = SCRIPT.read_text(encoding="utf-8")
    assert "if key != args.action_key:" in body
    assert "trying an older one" in body


def test_main_actually_asks_for_both_names(monkeypatch, tmp_path):
    """The helper spanning both names is useless if the caller passes one.

    This is the assertion the first draft of this file was missing: deleting
    the cell id from main()'s `names` list left every other test in here
    green while restoring nothing a merge-queue run could use.
    """
    module = load_module()
    seen: dict[str, list[str]] = {}

    def fake(repository, names, token):
        seen["names"] = list(names)
        return []

    monkeypatch.setattr(module, "reusable_outputs", fake)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setattr(
        "sys.argv",
        ["restore", "--cell-id", "hummingbird-x86_64",
         "--action-key", "sha256:abc", "--out-dir", str(tmp_path / "cell"),
         "--repository", "o/r"],
    )
    assert module.main() == 0
    assert seen["names"] == ["hummingbird-x86_64-partial", "hummingbird-x86_64"], (
        "main must offer the interrupted attempt AND the validated one"
    )
