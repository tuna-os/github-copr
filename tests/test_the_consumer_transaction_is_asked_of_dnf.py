"""The consumer's question is asked of dnf, inside the image, with only the
consumer's repositories: utah-packages' publish gate, taken verbatim in shape.

scripts/check-hummingbird-installability.py is a Requires: walk over
primary.xml -- necessary, not sufficient: version constraints, conflicts and
the base image's own rpmdb (which Hummingbird deliberately uses to supply
part of its dependency set) are dnf's job. utah-packages runs
`dnf --assumeno install <contract>` inside the pinned bootc-os image with
every other repository disabled and refuses to publish on a failed
transaction. scripts/check-hummingbird-installability-container.sh is that
step for this catalog's roots, per desktop, with the consumed repositories
(utah's GNOME) materialised out of their OCI images.

These tests hold the properties that make the gate honest without running
podman: the same roots the static walk uses, the same image tunaOS builds
from, --assumeno (nothing installs), every repository disabled but the
consumer's, no publish, no credentials, and a workflow that runs it on the
inputs that move it. The transaction itself runs in CI.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "check-hummingbird-installability-container.sh"
ROOTS = ROOT / "scripts" / "hummingbird-desktop-roots.py"
WORKFLOW = ROOT / ".github" / "workflows" / "hummingbird-installability.yml"
CATALOG = ROOT / "manifests" / "hummingbird-desktops.yaml"
FACTORY = ROOT / "manifests" / "package-factory.yaml"


def roots(*args: str) -> list[str]:
    out = subprocess.run([sys.executable, str(ROOTS), *args], capture_output=True, text=True, check=True)
    return out.stdout.split()


def test_the_roots_helper_lists_exactly_what_the_static_walk_walks():
    catalog = yaml.safe_load(CATALOG.read_text())
    assert roots("--list") == [d for d in catalog["desktops"] if d != "bluefin"]
    for desktop in roots("--list"):
        definition = catalog["desktops"][desktop]
        expected = list(dict.fromkeys(
            definition.get("required_packages", []) + definition.get("install_packages", [])))
        assert roots(desktop) == expected, desktop
    assert roots("--consumed-for", "gnome") == ["utah-packages"]
    assert roots("--consumed-for", "kde") == []


def test_an_unknown_desktop_is_an_error_not_an_empty_list():
    proc = subprocess.run([sys.executable, str(ROOTS), "plasma6"], capture_output=True, text=True)
    assert proc.returncode == 2 and "unknown desktop" in proc.stderr


def test_the_gate_asks_dnf_and_installs_nothing():
    text = GATE.read_text()
    assert "--assumeno" in text
    assert '--disablerepo="*"' in text, "every repository off, then only the consumer's on"
    for repo in ("public-hummingbird-*", "tunaos-hummingbird", "consumed-*"):
        assert f'--enablerepo="{repo}"' in text or f"--enablerepo={repo}" in text, repo
    assert "install_weak_deps=False" in text, "utah's transaction shape: weak deps would hide a hard miss"
    for forbidden in ("rclone", "R2_", "podman push", "cosign sign", "rpmsign"):
        assert forbidden not in text, f"the gate must not publish or sign ({forbidden})"
    assert "podman login" not in text, "public images pinned by digest need no credentials"


def test_the_gate_reads_the_contract_not_a_copy_of_it():
    """The image, the two indexes and the consumed repositories all come from
    manifests/package-factory.yaml at run time, so a pin bump there is a pin
    bump here -- no second literal to drift."""
    text = GATE.read_text()
    assert 'FACTORY="${ROOT}/manifests/package-factory.yaml"' in text
    for key in ("probe_image", "published_index", "target_index", "consumed_indexes"):
        assert key in text, key
    assert "quay.io/hummingbird-community" not in text, "the image is read from the contract, never hardcoded"
    assert "repo.tunaos.org" not in text, "the prefix is read from the contract, never hardcoded"


def test_the_gate_materialises_consumed_repositories_from_their_digests():
    text = GATE.read_text()
    assert 'ref="${consumed_ref[$id]#oci://}"' in text
    assert "podman create --pull=always" in text and "podman cp" in text
    # A repository-only image declares no CMD or ENTRYPOINT, and `podman
    # create` refuses one without an argv -- after pulling all 500 MB of it
    # (run 33656777961). The argv is recorded, never executed.
    assert 'podman create --pull=always "$ref" true' in text, (
        "podman create needs an explicit command for an image that declares "
        "no entrypoint"
    )
    # podman cp does not create the host directory; the first CI run died on
    # exactly that after pulling 500 MB (run 33619237851).
    assert text.index('mkdir -p "$work/consumed/${id}"') < text.index('podman cp "${container}:/repository/."')
    assert "baseurl=file:///consumed/" in text
    assert "priority=5" in text, "consumed beats the prefix (11), matching gnome.yaml's priorities on the tunaOS side"


def test_the_contract_the_gate_reads_is_complete():
    target = yaml.safe_load(FACTORY.read_text())["targets"]["hummingbird"]
    assert re.search(r"@sha256:[0-9a-f]{64}$", target["probe_image"]), "probe_image must be a digest"
    assert target["published_index"]["x86_64"].startswith("https://")
    assert "$arch" in target["gap_measurement"]["target_index"]
    for consumed in target["gap_measurement"]["consumed_indexes"]:
        assert consumed["index"].startswith("oci://") and "@sha256:" in consumed["index"]


def test_the_workflow_runs_the_gate_on_what_moves_it():
    wf = yaml.safe_load(WORKFLOW.read_text())
    on = wf.get("on") or wf.get(True)
    assert "schedule" in on and "workflow_dispatch" in on
    paths = set(on["pull_request"]["paths"])
    for path in ("scripts/check-hummingbird-installability-container.sh",
                 "scripts/hummingbird-desktop-roots.py",
                 "manifests/package-factory.yaml",
                 "manifests/hummingbird-desktops.yaml"):
        assert path in paths, path
    job = wf["jobs"]["container"]
    steps = "\n".join(step.get("run", "") for step in job["steps"])
    assert "check-hummingbird-installability-container.sh" in steps
    assert "GITHUB_STEP_SUMMARY" in steps, "the report is the product"
    assert "--fail-on-unresolved" not in steps, (
        "advisory until a desktop first resolves; flipping it is a deliberate edit"
    )
    assert wf["permissions"] == {"contents": "read"}
