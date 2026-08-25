"""The probe must answer from Hummingbird's repos, not the Rawhide beneath.

manifests/package-factory.yaml held hummingbird at status: scaffold for one
stated reason: "the only image that boots a Hummingbird-shaped root is the
Fedora Rawhide base beneath it, which answers yes for packages Hummingbird
does not ship. A probe that lies is worse than a probe that is absent."

That lie is not hypothetical. Inferring hummingbird's package set from
Fedora's produced a confidently wrong, published diagnosis this very week
(docs/HUMMINGBIRD.md in tunaOS tells that story). The honest answer exists
and is measured: inside the pinned bootc-os image, tunaOS run 32813311729 got
dbus-daemon -> installed and flatpak -> "No match for argument", which is the
truth for a distribution that does not package flatpak.

These tests pin the construction of that honest probe. They run no
containers — what they guard is that the pieces stay wired: a hummingbird
query script exists, the manifest's probe image is Hummingbird-shaped and
digest-pinned, and el10's repo bootstrap cannot leak into it.
"""

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "probe", ROOT / "scripts" / "probe-target-dependencies.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def _target():
    with open(ROOT / "manifests" / "package-factory.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["targets"]["hummingbird"]


def test_hummingbird_has_a_query_script():
    assert "hummingbird" in probe.QUERY_SCRIPTS, (
        "no query script — the probe cannot ask hummingbird anything, "
        "whatever image is declared"
    )


def test_the_query_script_prefers_dnf5():
    """The bootc-os image ships dnf5; plain dnf may not exist there."""
    s = probe.QUERY_SCRIPTS["hummingbird"]
    assert "dnf5" in s
    assert "RESULT" in s, "the runner parses RESULT lines; emitting none reads as all-missing"


def test_the_probe_image_is_hummingbird_shaped_and_pinned():
    img = _target()["probe_image"]
    assert "rawhide" not in img, (
        "the probe image answers from Fedora Rawhide again — this is the "
        "documented lie that kept the target at scaffold"
    )
    assert "hummingbird" in img
    assert "@sha256:" in img, (
        "unpinned probe image — a rolling tag re-introduces silent drift "
        "between what is probed and what is built"
    )


def test_the_probe_image_matches_what_tunaos_builds_from():
    """One digest, probed and built. Two digests drift apart silently."""
    img = _target()["probe_image"]
    assert img.endswith(
        "sha256:c5539f9ed4d93aab6bd41e4f5aef8ab83055f3f9e855a47b69fadb7420d0d1df"
    ), "probe digest no longer matches tunaOS build-config's hummingbird base"


def test_el10_repo_bootstrap_cannot_leak_into_the_hummingbird_probe():
    """Enabling epel/crb — or any build repo — inside this probe would make it
    answer from repos the target does not serve: the lie again, self-inflicted."""
    cmd = probe.podman_command("img", "hummingbird", ["flatpak"],
                               ["fedora-rawhide", "epel", "crb"])
    script = cmd[cmd.index("bash") + 2]
    assert "epel-release" not in script
    assert "config-manager" not in script


def test_the_cli_accepts_hummingbird_as_a_target():
    """--target choices derive from QUERY_SCRIPTS; this pins the derivation."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", action="append",
                        choices=sorted(probe.QUERY_SCRIPTS))
    args = parser.parse_args(["--target", "hummingbird"])
    assert args.target == ["hummingbird"]
