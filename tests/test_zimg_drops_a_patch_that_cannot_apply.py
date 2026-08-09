"""zimg could not build, and Fedora's rawhide spec cannot build it either.

Rawhide's zimg ships the release-3.0.6 tarball with two upstream commits
applied by `%autosetup -p1`. The second, 0e56801 ("colorspace: fix AVX2
check"), rewrites

    if (!ret && caps.avx)          ->    if (!ret && caps.avx2)
            ret = create_matrix_operation_avx2(m);

and `create_matrix_operation_avx2` does not exist anywhere in release-3.0.6 --
its only occurrence in an unpacked 3.0.6 tree is inside the .rej file the
failed patch leaves behind. Upstream added the AVX2 dispatcher after the
release; 3.0.6 guards an AVX call with caps.avx, which is correct as written.
The patch therefore fixes a bug this version does not have.

Reproduced locally against Fedora's own pinned tarball -- SHA512 verified
against dist-git `sources` -- with rpm's exact flags:

    Patch0 OK
    Hunk #1 FAILED at 16.
    1 out of 1 hunk FAILED -- saving rejects to ...operation_impl_x86.cpp.rej

That is what failed src/hummingbird/zimg in run 31294475023 and, before it,
the kde-00 tier. Rawhide's published binary is 3.0.6-3.fc44 -- a dist tag one
release behind rawhide's current F45, which is consistent with no F45 build
having succeeded since the patch was added, though it does not prove it.

So this vendors Fedora's packaging with that one patch dropped. Dropping it is
the fix rather than a workaround: there is nothing in 3.0.6 for it to fix.
Patch0 ("Fix build with GCC 15") is kept -- it applies, and Rawhide is on
GCC 16.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
VENDORED = REPO / "src" / "hummingbird" / "zimg"
SPEC = VENDORED / "zimg.spec"
BUILD_ORDER = REPO / "build-order-hummingbird-desktops.yml"

AVX2_PATCH = "0e56801f98db3e363c974fca794fa06022d40ee4"
GCC15_PATCH = "b013c7b006e6bee05b7964162f3a00402168e77f"


@pytest.fixture(scope="module")
def spec_text():
    return SPEC.read_text()


def test_the_packaging_is_vendored_not_imported() -> None:
    """An in-tree directory is what stops the workflow re-importing rawhide.

    The import step is `if [ -d "$pkg_path" ]; then ... nothing to import`, so
    the directory's existence is the whole mechanism -- exactly how
    src/hummingbird/SwayNotificationCenter works. Without it every run would
    pull the broken spec back down and fail again.
    """
    assert SPEC.is_file(), "no vendored spec, so rawhide's broken one is used"
    assert (VENDORED / "sources").is_file(), "no sources file to pin the tarball"


def test_the_inapplicable_patch_is_gone(spec_text: str) -> None:
    assert AVX2_PATCH not in spec_text, (
        "the AVX2 patch is back; it cannot apply to release-3.0.6 and %autosetup "
        "-p1 will fail %prep"
    )


def test_the_gcc_patch_is_kept(spec_text: str) -> None:
    """Dropping both patches would be the lazy fix and would break the build."""
    assert GCC15_PATCH in spec_text, (
        "the GCC 15 build fix was dropped too; rawhide is on GCC 16 and needs it"
    )


def test_the_reason_travels_with_the_spec(spec_text: str) -> None:
    """A silently-missing patch reads as an oversight and gets 'restored'."""
    assert "create_matrix_operation_avx2" in spec_text, (
        "the spec does not say why the patch is absent, so the next person to "
        "diff it against rawhide will put it back"
    )


def test_the_tarball_is_the_one_fedora_pinned() -> None:
    """Verified by download: this SHA512 is what src.fedoraproject.org serves.

    It matters because the failure was very nearly misattributed to this
    repo's own source-fetching bug -- the one 81e2b78 fixed, which did serve
    the wrong bytes for luajit and wildmidi. Pinning Fedora's checksum is what
    rules that explanation out for zimg.
    """
    sources = (VENDORED / "sources").read_text()
    assert sources.strip() == (
        "SHA512 (zimg-3.0.6.tar.gz) = 98d7d65085530e0e1d3e25218608867f1e8d978fc"
        "759777efe2e6034baa31db10f1dda46ef8e00ec6f3c23b91aea839da076bfa4fcb75d9"
        "8111a08513f45506d"
    ), "the pinned tarball checksum changed; re-verify against dist-git sources"


def test_the_build_order_no_longer_imports_it() -> None:
    """`distgit:` and a vendored directory together are a contradiction.

    scripts/measure-hummingbird-gap.py emits `distgit:` only when
    src/hummingbird/<name> is NOT a directory, so a regeneration drops the key
    on its own -- this asserts the committed file already agrees, rather than
    waiting for the next regeneration to notice.
    """
    lines = BUILD_ORDER.read_text().splitlines()
    hits = [i for i, l in enumerate(lines) if l.strip() == "- path: src/hummingbird/zimg"]
    assert len(hits) == 1, f"expected zimg once in the build order, found {len(hits)}"
    following = lines[hits[0] + 1].strip()
    assert not following.startswith("distgit:"), (
        "the build order still imports zimg from dist-git, which would overwrite "
        "the vendored spec with the broken one"
    )
