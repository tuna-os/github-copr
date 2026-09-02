"""The simulator's pure parts: cfg parsing, rich deps, priority masking.

The end-to-end validations (re-discovering dconf pre-#548 and the '+'-files
pre-#551) need the live indexes and run as script modes (--drop-repo /
--no-excludes), recorded in the PR that lands this. These tests pin the
mechanisms those validations rest on, against fixtures, so CI stays fast.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location(
        "sim", ROOT / "scripts" / "simulate-buildroot-resolution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sim = load()


# ---- mock config parsing --------------------------------------------------

def test_repos_come_from_the_real_mock_config():
    repos = sim.parse_mock_repos(ROOT / "mock" / "hummingbird-ci.cfg")
    by_id = {r["id"]: r for r in repos}
    assert by_id["hummingbird"]["priority"] == 10
    assert by_id["tunaos-hummingbird"]["priority"] == 11
    # #551's excludes must reach the simulator, or it models a buildroot
    # that no longer exists.
    assert "*+*" in by_id["tunaos-hummingbird"]["excludepkgs"]
    assert "libcdio-paranoia*" in by_id["tunaos-hummingbird"]["excludepkgs"]
    # includepkgs pins confine the F44 repos; without them the simulator
    # would let all of F44 shadow Rawhide at priority 50.
    assert "python3-*" in by_id["fedora-44-python"]["includepkgs"]
    # local-build is file:// and modeled through the build set instead.
    assert "local-build" not in by_id


def test_metalink_repos_resolve_to_a_concrete_baseurl():
    repos = sim.parse_mock_repos(ROOT / "mock" / "hummingbird-ci.cfg")
    f44 = next(r for r in repos if r["id"] == "fedora-44-python")
    assert f44["baseurl"].startswith("https://dl.fedoraproject.org/")


# ---- rich dependency parsing ----------------------------------------------

def test_the_dconf_killer_parses():
    """The exact expression that blocked publishing for five days."""
    tree = sim.parse_rich("(python(abi) = 3.15 if python3)")
    assert tree == ("if", ("leaf", "python(abi)", "=", "0:3.15"),
                    ("leaf", "python3", None, None), None)


@pytest.mark.parametrize("expr,shape", [
    ("(a and b)", "and"),
    ("(a or b)", "or"),
    ("(a with b)", "and"),
    ("(a if b else c)", "if"),
    ("(a unless b)", "unless"),
])
def test_common_forms_parse(expr, shape):
    tree = sim.parse_rich(expr)
    assert tree is not None and tree[0] == shape, (expr, tree)


def test_garbage_is_none_not_a_guess():
    assert sim.parse_rich("(a frobnicates b)") is None
    assert sim.parse_rich("(unbalanced") is None


# ---- the buildroot model --------------------------------------------------

def inst(name, repo, priority, provides=(), requires=(), evr="0:1-1",
         href=None, srpm=None):
    return {"name": name, "evr": evr, "repo": repo, "priority": priority,
            "baseurl": f"https://example/{repo}/", "href": href or f"{name}.rpm",
            "provides": list(provides), "requires": list(requires),
            "files": [], "srpm": srpm}


def test_priority_masks_a_name_across_repos():
    """The mechanism that killed dconf: hummingbird's python3 at priority 10
    drops Rawhide's python3 entirely, so python(abi) = 3.15 has no surviving
    provider even though Rawhide carries one."""
    br = sim.Buildroot([
        inst("python3", "hummingbird", 10, provides=[("python(abi)", "0:3.14")]),
        inst("python3", "fedora", 99, provides=[("python(abi)", "0:3.15")]),
        inst("gobject-introspection-devel", "fedora", 99,
             requires=[("(python(abi) = 3.15 if python3)", None, None)]),
    ], build_set_srpms=set())
    gi = br.by_name["gobject-introspection-devel"][0]
    assert br.installable(gi) is False
    assert "python(abi)" in br.why(gi)


def test_a_priority_11_copy_unmasks_the_block():
    """#548's fix, in miniature: our own g-i-devel at priority 11 masks
    Rawhide's, and ours requires the interpreter the chroot actually has."""
    br = sim.Buildroot([
        inst("python3", "hummingbird", 10, provides=[("python(abi)", "0:3.14")]),
        inst("python3", "fedora", 99, provides=[("python(abi)", "0:3.15")]),
        inst("gobject-introspection-devel", "tunaos-hummingbird", 11,
             requires=[("(python(abi) = 3.14 if python3)", None, None)]),
        inst("gobject-introspection-devel", "fedora", 99,
             requires=[("(python(abi) = 3.15 if python3)", None, None)]),
    ], build_set_srpms=set())
    survivors = br.by_name["gobject-introspection-devel"]
    assert [s["repo"] for s in survivors] == ["tunaos-hummingbird"]
    assert br.installable(survivors[0]) is True


def test_versioned_requirement_checks_the_provider_evr():
    br = sim.Buildroot([
        inst("libnotify", "hummingbird", 10, evr="0:0.8.6-1",
             provides=[("libnotify", "0:0.8.6-1")]),
        inst("gnome-settings-daemon", "fedora", 99,
             requires=[("libnotify", ">=", "0:0.8.7")]),
    ], build_set_srpms=set())
    gsd = br.by_name["gnome-settings-daemon"][0]
    assert br.installable(gsd) is False


def test_a_build_set_product_satisfies_before_it_is_published():
    """Tier N's output lands in local-build before tier N+1 resolves, so a
    requirement provided only by a build-set member must not read BLOCKED."""
    br = sim.Buildroot([
        inst("gnome-shell", "fedora", 99, srpm="gnome-shell-51~beta-1.fc45.src.rpm",
             provides=[("gnome-shell", "0:51~beta-1")],
             requires=[("nonexistent-thing", None, None)]),
        inst("consumer", "fedora", 99, requires=[("gnome-shell", None, None)]),
    ], build_set_srpms={"gnome-shell"})
    consumer = br.by_name["consumer"][0]
    assert br.installable(consumer) is True


def test_dependency_cycles_do_not_hang_or_block():
    br = sim.Buildroot([
        inst("a", "fedora", 99, requires=[("b", None, None)]),
        inst("b", "fedora", 99, requires=[("a", None, None)]),
    ], build_set_srpms=set())
    assert br.installable(br.by_name["a"][0]) is True


def test_a_missing_file_dep_is_unverified_not_blocked():
    """primary.xml carries only a subset of file lists; inventing a verdict
    from an incomplete index is how a tool teaches people to ignore it."""
    br = sim.Buildroot([
        inst("x", "fedora", 99, requires=[("/usr/bin/mystery", None, None)]),
    ], build_set_srpms=set())
    assert br.installable(br.by_name["x"][0]) is None
