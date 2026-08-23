"""The deb backport gap must be computed, and computed with the right rule.

RFC 011's gap engine is rpm-md only -- measure-target-gap.py is a shim over
measure-hummingbird-gap.py, which parses primary.xml and knows nothing about
APT. scripts/measure-deb-backport-gap.py is the deb half, and it answers a
different question: Hummingbird asks what a target fails to PROVIDE and closes
over Requires:, while a backport asks what must be REBUILT and closes over
Build-Depends:, because the packaging already exists in the donor suite.

The rule that bounds the closure is the interesting part, and the first
version of it was WRONG. "Include a build dependency when the donor's version
is newer than the target's" sounds right and is not: measured against Ubuntu
stonking, nearly every source in a devel suite is newer than in an LTS, so the
closure swallowed the archive and reported 1263 packages -- swig, gettext,
node-mocha, ruby-rspec, the Go toolchain. With the constraint honoured the
same measurement reports 16, all of them real GNOME-stack packages.

So the rule is: a build dependency forces a rebuild only when the target
FAILS A DECLARED CONSTRAINT. An unversioned build-dep is satisfied by the
target having the package at all, which is what keeps the toolchain out.
"""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "measure_deb_backport_gap", ROOT / "scripts" / "measure-deb-backport-gap.py"
)
gap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gap)


def test_a_tilde_sorts_below_the_release_it_precedes():
    """Load-bearing: every donor version in the manifest today is a ~alpha or
    ~beta, so a comparator that got this backwards would report the whole
    stack as already satisfied and measure a gap of zero."""
    assert gap.compare_versions("51~beta", "51") < 0
    assert gap.compare_versions("51~alpha", "51~beta") < 0
    assert gap.compare_versions("50.1", "51~beta") < 0
    assert gap.compare_versions("51", "51") == 0


def test_epoch_and_revision_follow_dpkg():
    assert gap.compare_versions("1:50.0", "50.9") > 0
    assert gap.compare_versions("1.0-1", "1.0-2") < 0
    assert gap.compare_versions("1.0", "1.0-1") < 0
    assert gap.compare_versions("2.88.0", "2.89.3") < 0


def test_an_unversioned_build_dep_is_satisfied_by_mere_presence():
    """This single rule is what separates 16 packages from 1263."""
    assert gap.satisfies("11.7.5", "", "") is True
    assert gap.satisfies(None, "", "") is False


def test_a_version_floor_is_enforced():
    assert gap.satisfies("2.88.0", ">=", "2.89.0") is False
    assert gap.satisfies("2.89.3", ">=", "2.89.0") is True
    assert gap.satisfies("1.0", ">>", "1.0") is False


def test_clauses_keep_their_constraints():
    stanza = {"Build-Depends": "debhelper, libglib2.0-dev (>= 2.89.0) [amd64], a | b"}
    clauses = gap.build_dep_clauses(stanza)
    assert ["debhelper", "", ""] == list(clauses[0][0])
    assert ["libglib2.0-dev", ">=", "2.89.0"] == list(clauses[1][0])
    assert [name for name, _, _ in clauses[2]] == ["a", "b"]


def test_a_newer_donor_dep_alone_does_not_force_a_rebuild():
    """The 1263-package regression, in miniature. `tool` is newer in the donor
    but the build-dep is unversioned, so it must NOT enter the closure."""
    donor = {
        "app": {"Package": "app", "Version": "51~beta-1", "Binary": "app",
                "Build-Depends": "tool"},
        "tool": {"Package": "tool", "Version": "2.0", "Binary": "tool"},
    }
    target = {
        "app": {"Package": "app", "Version": "50.0-1", "Binary": "app"},
        "tool": {"Package": "tool", "Version": "1.0", "Binary": "tool"},
    }
    target_binary = {"app": "50.0-1", "tool": "1.0"}
    result = gap.measure(["app"], donor, target, gap.binary_to_source(donor), target_binary)
    assert set(result["needed"]) == {"app"}, result["needed"]


def test_a_failed_version_floor_does_force_a_rebuild():
    """The same shape, with a constraint the target cannot meet."""
    donor = {
        "app": {"Package": "app", "Version": "51~beta-1", "Binary": "app",
                "Build-Depends": "tool (>= 2.0)"},
        "tool": {"Package": "tool", "Version": "2.0", "Binary": "tool"},
    }
    target = {
        "app": {"Package": "app", "Version": "50.0-1", "Binary": "app"},
        "tool": {"Package": "tool", "Version": "1.0", "Binary": "tool"},
    }
    target_binary = {"app": "50.0-1", "tool": "1.0"}
    result = gap.measure(["app"], donor, target, gap.binary_to_source(donor), target_binary)
    assert set(result["needed"]) == {"app", "tool"}, result["needed"]
    # tool must build BEFORE app, so it sits in an earlier tier.
    order = gap.tiers(result["needed"])
    assert order[0] == ["tool"] and order[-1] == ["app"], order


def test_a_target_that_has_caught_up_needs_nothing():
    """The engine retires itself. Once a suite ships the stack, the answer is
    zero without anyone editing the manifest -- which is why debian/sid is
    listed even though it will get GNOME 51 on its own."""
    donor = {"app": {"Package": "app", "Version": "51.0-1", "Binary": "app"}}
    target = {"app": {"Package": "app", "Version": "51.0-1", "Binary": "app"}}
    result = gap.measure(["app"], donor, target, gap.binary_to_source(donor), {"app": "51.0-1"})
    assert result["needed"] == {}


def test_the_manifest_only_names_declared_targets():
    import yaml
    manifest = yaml.safe_load((ROOT / "manifests" / "gnome51-deb.yaml").read_text())
    contract = yaml.safe_load((ROOT / "manifests" / "package-factory.yaml").read_text())
    for name in manifest["targets"]:
        assert name in contract["targets"], name
        assert contract["targets"][name]["format"] == "deb", name
    assert manifest["roots"], "a gap over no roots measures nothing"
