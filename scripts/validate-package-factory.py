#!/usr/bin/env python3
"""Validate the cross-distro package-factory target contract."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def gate_targets(workflows: list[Path]) -> set[str]:
    """Return every target name the Tideforge gate workflows actually exercise.

    A cell counts only if it names a target, either as an explicit `target:`
    matrix key or via `tideforge.py render --target <name>`. Reading the
    workflows rather than trusting a hand-maintained list is the whole point:
    the list is what went stale.
    """
    exercised: set[str] = set()
    for workflow in workflows:
        if not workflow.exists():
            continue
        text = workflow.read_text()
        # `--target "${{ matrix.target }}"` names a target indirectly; the
        # literal value comes from that job's matrix `target:` keys, which the
        # second pattern collects. Skip the expression itself so it does not
        # enter the set as a target literally called "matrix.target".
        for match in re.finditer(r"--target\s+\"?([a-z0-9-]+)\b", text):
            exercised.add(match.group(1))
        for match in re.finditer(r"^\s*target:\s*([a-z0-9-]+)\s*$", text, re.MULTILINE):
            exercised.add(match.group(1))
        # A matrix axis exercises its targets just as much as an include list
        # does -- `target: [hummingbird]` or a block list under `target:`. Only
        # recognising the include form meant a job matrixed over targets read
        # as covering none of them, which is the same false negative this
        # function exists to prevent, wearing a different hat.
        for match in re.finditer(r"^\s*target:\s*\[([^\]]+)\]\s*$", text, re.MULTILINE):
            for name in match.group(1).split(","):
                name = name.strip().strip("\"'")
                if re.fullmatch(r"[a-z0-9-]+", name):
                    exercised.add(name)
    return exercised


def check_gate_coverage(targets: set[str], workflows: list[Path]) -> None:
    """Fail when a declared target has no cells in the gate.

    openSUSE was declared with its own architectures and r2_path, 19 recipes
    opted into it, and it still had zero cells for months (#139). Nothing
    failed, because nothing was looking. A target that is never exercised must
    not be indistinguishable from one that passes.
    """
    exercised = gate_targets(workflows)
    uncovered = sorted(target for target in targets if target not in exercised)
    if uncovered:
        fail(
            f"declared target(s) with zero cells in the Tideforge gate: {uncovered}. "
            "Every target in package-factory.yaml must be exercised by at least one "
            "job, or it is untested while looking supported. See #139."
        )
    print(f"Gate coverage: all {len(targets)} declared targets are exercised")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--gate-workflow",
        type=Path,
        action="append",
        default=None,
        help="Tideforge gate workflow to scan for target coverage (repeatable)",
    )
    args = parser.parse_args()
    data = yaml.safe_load(args.manifest.read_text())
    if data.get("schema") != 1:
        fail("schema must be 1")

    seen_upstreams: set[str] = set()
    for upstream in data.get("upstreams", []):
        upstream_id = upstream.get("id", "")
        if not upstream_id or upstream_id in seen_upstreams:
            fail(f"invalid or duplicate upstream id: {upstream_id!r}")
        if not upstream.get("url", "").startswith("https://"):
            fail(f"{upstream_id}: URL must use HTTPS")
        if upstream.get("license_review") != "required":
            fail(f"{upstream_id}: license_review must be required")
        seen_upstreams.add(upstream_id)

    targets = data.get("targets", {})
    required = {"el10", "ubuntu", "debian", "hummingbird", "opensuse-tumbleweed", "arch"}
    if set(targets) != required:
        fail(f"targets must be exactly {sorted(required)}")
    for target_id, target in targets.items():
        if target.get("status") not in {"supported", "scaffold"}:
            fail(f"{target_id}: status must be supported or scaffold")
        for field in ("format", "architectures", "r2_path", "repository", "probe_image"):
            if not target.get(field):
                fail(f"{target_id}: {field} is required")
        if "/" not in target["probe_image"]:
            fail(f"{target_id}: probe_image must be a fully-qualified container image")
        # hummingbird/ is rpm-md like rpm/, but it is an overlay on somebody
        # else's distribution rather than a TunaOS repository, and its path is
        # already published with the desktop packages in it. Moving it under
        # rpm/ to satisfy this check would orphan them.
        if not target["r2_path"].startswith(("rpm/", "apt/", "pacman/", "hummingbird/")):
            fail(f"{target_id}: r2_path has an unsupported namespace")
        if not all(arch in {"x86_64", "aarch64", "amd64", "arm64"} for arch in target["architectures"]):
            fail(f"{target_id}: unsupported architecture")
        build_repositories = target.get("build_repositories", [])
        if not isinstance(build_repositories, list) or not all(
            isinstance(repository, str) and repository for repository in build_repositories
        ):
            fail(f"{target_id}: build_repositories must be a list of non-empty names")
    print("Package factory manifest: valid")

    workflows = args.gate_workflow
    if workflows is None:
        workflow_directory = args.manifest.parent.parent / ".github" / "workflows"
        workflows = [
            workflow_directory / "build-tideforge-supported.yml",
            workflow_directory / "build-tideforge-arch.yml",
            # Hummingbird's desktop packages are dist-git imports rather than
            # recipes, so they are built by their own workflow -- but a target
            # exercised somewhere else is still exercised, and leaving this out
            # would make hummingbird look uncovered when it is the busiest
            # target in the repository.
            workflow_directory / "build-hummingbird-desktops.yml",
        ]
    check_gate_coverage(set(targets), workflows)


if __name__ == "__main__":
    main()
