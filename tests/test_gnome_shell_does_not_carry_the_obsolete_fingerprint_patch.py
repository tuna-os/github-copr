"""gnome-shell must not carry a downstream patch that targets code upstream deleted.

0001-gdm-Work-around-failing-fingerprint-auth.patch targeted js/gdm/util.js's
ShellUserVerifier class: a wall-clock heuristic ("if fingerprint auth fails
within one second of starting, treat it as unavailable rather than a real
failure") working around unconfigured PAM / no enrolled prints.

Confirmed against gitlab.gnome.org/GNOME/gnome-shell at tag 51.beta -- the
exact tag this spec builds: js/gdm/util.js has been refactored down to 39
lines (an unrelated clone-fade-actor helper). ShellUserVerifier and all
fingerprint-verification logic moved to js/gdm/authServicesLegacy.js, whose
own _handleOnProblem() already implements a strictly better fix for the
same underlying problem -- a real retry counter (_failCounter/_canRetry(),
from the shared AuthServices base class in js/gdm/authServices.js) instead
of a timing heuristic. The patch is not stale context to rebase, it targets
code that no longer exists at all -- every hunk fails:

    error: while searching for:
    error: patch failed: js/gdm/util.js:113
    error: patch failed: js/gdm/util.js:672
    error: patch failed: js/gdm/util.js:766
    error: patch failed: js/gdm/util.js:838
    error: Bad exit status from /var/tmp/rpm-tmp.X1xtAE (%prep)

Removed the Patch: line, its comment, and the patch file. The OTHER patch
(gnome-shell-favourite-apps-firefox.patch) is untouched -- it wasn't
implicated in the failure and still applies cleanly.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = ROOT / "src/gnome-51/gnome-shell/gnome-shell.spec"
PATCH_FILE = ROOT / "src/gnome-51/gnome-shell/0001-gdm-Work-around-failing-fingerprint-auth.patch"
OTHER_PATCH_FILE = ROOT / "src/gnome-51/gnome-shell/gnome-shell-favourite-apps-firefox.patch"


def test_the_obsolete_patch_file_is_gone():
    assert not PATCH_FILE.exists(), (
        "0001-gdm-Work-around-failing-fingerprint-auth.patch reappeared -- "
        "it targets js/gdm/util.js's ShellUserVerifier, which no longer "
        "exists at gnome-shell 51.beta (refactored to "
        "js/gdm/authServicesLegacy.js, which already has a better fix); "
        "every hunk fails and aborts %prep"
    )


def test_the_spec_does_not_reference_the_obsolete_patch():
    text = SPEC.read_text(encoding="utf-8")
    assert "0001-gdm-Work-around-failing-fingerprint-auth.patch" not in text, (
        "gnome-shell.spec still references the removed fingerprint-auth "
        "patch file"
    )


def test_the_other_patch_is_undisturbed():
    """Sanity check the fix didn't over-remove: the unrelated firefox
    favourite-apps patch must still be referenced and still exist."""
    text = SPEC.read_text(encoding="utf-8")
    assert "gnome-shell-favourite-apps-firefox.patch" in text
    assert OTHER_PATCH_FILE.exists()
