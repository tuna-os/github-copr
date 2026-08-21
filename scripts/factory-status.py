#!/usr/bin/env python3
"""Generate docs/FACTORY-STATUS.md: what the factory has built, per target,
and what the catalog says is still needed.

RFC 011 Phase 1, first increment. Phase 0 gave the factory one catalog of
intent (manifests/catalog.yaml); until now the only way to answer "is this
package actually published for that target?" was to grep a primary.xml by
hand. This tool makes the answer a generated artifact with provenance:

  * for every target in manifests/package-factory.yaml that declares a
    `published_index` (the SERVED read URL(s) of its published repository —
    distinct from `r2_path`, the bucket write path), fetch every live
    rpm-md index it names and classify every catalog entry targeting it as
    BUILT (some binary or source package of that name is in one of them) or
    NEEDED. An arch may declare more than one index because a target can
    have more than one publisher (#467); BUILT is the union, because a
    buildroot pointed at that target sees all of them;
  * for the hummingbird target, additionally measure each desktop's
    `required_packages` roots against the index — the per-desktop coverage
    table that decides which desktops tunaOS can wire (tunaOS#1755);
  * flat apt indexes (the tideforge deb repos) are read natively: Package:
    and Source: names from Packages.gz;
  * targets whose repository format this tool cannot read yet (pacman) are
    REPORTED as unmeasured with their entry counts — never silently
    dropped, per the no-silent-caps rule.

Everything is measured from live indexes; nothing is inferred from names or
memory. factory-status.json records the repomd revision and primary.xml
checksum every answer came from.

The full dependency-closure measurement (what a desktop transitively needs
that no repo supplies) remains scripts/measure-hummingbird-gap.py; its
target-parameterized generalization is the rest of RFC 011 Phase 1 and
arrives with the family-by-family build-order conversions.

Usage:
    scripts/factory-status.py                      # writes docs/ artifacts
    scripts/factory-status.py --check-structure    # no network: validates
                                                   # config shape for CI
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import importlib.util
import json
import pathlib
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]

# repo.tunaos.org sits behind Cloudflare, which 403s python-urllib's default
# User-Agent while serving curl fine (measured 2026-08-18). Install a named
# opener globally so the fetcher imported below inherits it too.
_opener = urllib.request.build_opener()
_opener.addheaders = [(
    "User-Agent",
    "tunaos-factory-status/1 (+https://github.com/tuna-os/tunaos-packages)",
)]
urllib.request.install_opener(_opener)

# measure-hummingbird-gap.py owns the rpm-md machinery (fetch, repomd
# resolution, primary.xml parsing, srpm name derivation). Import it as a
# module rather than copying any of it — one implementation of index reading
# is the point of RFC 011.
_spec = importlib.util.spec_from_file_location(
    "mhg", ROOT / "scripts" / "measure-hummingbird-gap.py"
)
mhg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mhg)

sys.path.insert(0, str(ROOT / "scripts"))
import published_index as pubidx  # noqa: E402  (needs the path above)


def load_yaml(path: pathlib.Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def index_names(baseurl: str, cache: pathlib.Path) -> tuple[set, dict]:
    """All names an index can answer for: binary names + source names."""
    blob, provenance = mhg.primary_of(baseurl, cache)
    parsed = mhg.parse_primary(blob)
    names = set(parsed["packages"])
    for info in parsed["packages"].values():
        source = mhg.srpm_name(info.get("srpm"))
        if source:
            names.add(source)
    provenance["package_names"] = len(parsed["packages"])
    return names, provenance


def apt_index_names(baseurl: str, cache: pathlib.Path) -> tuple[set, dict]:
    """All names a flat apt repo can answer for: Package: + Source: names.

    The tideforge deb repos are flat apt-ftparchive layouts (Packages.gz at
    the repo root — publish-tideforge-debs.yml). Source: may carry a
    ' (version)' suffix, which is stripped so the catalog's source names
    match.
    """
    base = baseurl.rstrip("/") + "/"
    raw = mhg.fetch(base + "Packages.gz", cache)
    text = gzip.decompress(raw).decode("utf-8", "replace")
    names: set = set()
    packages = 0
    for line in text.splitlines():
        if line.startswith("Package:"):
            names.add(line.split(":", 1)[1].strip())
            packages += 1
        elif line.startswith("Source:"):
            names.add(line.split(":", 1)[1].strip().split(" ", 1)[0])
    provenance = {
        "baseurl": base,
        "packages_gz_sha256": hashlib.sha256(raw).hexdigest(),
        "package_names": packages,
    }
    return names, provenance


def measure(catalog, factory, cache: pathlib.Path) -> dict:
    report = {
        "measured_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "targets": {},
        "unmeasured_targets": {},
    }
    entries = catalog["packages"]
    for target_id, target in factory["targets"].items():
        # set(): the same package can be catalogued by several families for
        # one target (e.g. cosmic-* by both the el10 COPR-replacement and
        # tideforge families); the question here is per NAME, not per entry.
        wanted = sorted({e["name"] for e in entries if target_id in e.get("targets", [])})
        published = target.get("published_index")
        if not published:
            report["unmeasured_targets"][target_id] = {
                "format": target.get("format"),
                "catalog_entries": len(wanted),
                "reason": "no published_index declared in package-factory.yaml",
            }
            continue
        readers = {"rpm": index_names, "deb": apt_index_names}
        reader = readers.get(target.get("format"))
        if reader is None:
            report["unmeasured_targets"][target_id] = {
                "format": target.get("format"),
                "catalog_entries": len(wanted),
                "reason": "only rpm-md and flat apt indexes are readable so far",
            }
            continue
        arches = {}
        for arch, declared in published.items():
            # An arch may declare several indexes (#467). BUILT is a union:
            # the question is whether a buildroot pointed at this target can
            # resolve the name, and it is pointed at all of them.
            names: set = set()
            provenances = []
            for url in pubidx.normalise(declared):
                found, provenance = reader(url, cache)
                names |= found
                provenances.append(provenance)
            built = sorted(n for n in wanted if n in names)
            needed = sorted(n for n in wanted if n not in names)
            arches[arch] = {
                "indexes": provenances,
                "catalog_entries": len(wanted),
                "built": built,
                "needed": needed,
            }
        report["targets"][target_id] = arches
    return report


def measure_hummingbird_desktops(report: dict, cache: pathlib.Path) -> None:
    """Per-desktop required_packages coverage against the published index."""
    manifest = load_yaml(ROOT / "manifests" / "hummingbird-desktops.yaml")
    hb = report["targets"].get("hummingbird")
    if not hb or "x86_64" not in hb:
        return
    names: set = set()
    for provenance in hb["x86_64"]["indexes"]:
        found, _ = index_names(provenance["baseurl"], cache)
        names |= found
    desktops = {}
    for desktop, spec in sorted(manifest.get("desktops", {}).items()):
        roots = spec.get("required_packages", [])
        missing = sorted(r for r in roots if r not in names)
        desktops[desktop] = {
            "roots": len(roots),
            "present": len(roots) - len(missing),
            "missing": missing,
        }
    report["hummingbird_desktops"] = desktops


def render(report: dict) -> str:
    lines = [
        "# Factory status — built vs needed, per target",
        "",
        "<!-- GENERATED by scripts/factory-status.py — do not hand-edit."
        " Regenerate: scripts/factory-status.py -->",
        "",
        f"Measured {report['measured_at']} from the live published indexes;",
        "provenance (repomd revision, primary.xml sha256) is in",
        "`docs/factory-status.json`, which also carries the full built and",
        "needed lists this page truncates.",
        "",
        "A catalog entry is **built** when the target's published index",
        "carries a binary or source package of that name, **needed** when it",
        "does not. This is presence, not freshness — version-level staleness",
        "needs catalog version pins, which most entries do not carry yet.",
        "",
    ]
    for target_id, arches in sorted(report["targets"].items()):
        lines.append(f"## {target_id}")
        lines.append("")
        lines.append("| arch | catalog entries | built | needed | index packages |")
        lines.append("|---|---|---|---|---|")
        for arch, data in sorted(arches.items()):
            lines.append(
                f"| {arch} | {data['catalog_entries']} | {len(data['built'])} "
                f"| {len(data['needed'])} | "
                f"{sum(i['package_names'] for i in data['indexes'])} |"
            )
        lines.append("")
        for arch, data in sorted(arches.items()):
            needed = data["needed"]
            if not needed:
                continue
            shown = needed[:40]
            lines.append(
                f"Needed on {arch} ({len(needed)}"
                f"{'; first 40, full list in the JSON' if len(needed) > 40 else ''}):"
            )
            lines.append("")
            lines.append("```")
            lines.extend(shown)
            lines.append("```")
            lines.append("")
    if report.get("hummingbird_desktops"):
        lines.append("## hummingbird desktop coverage (x86_64)")
        lines.append("")
        lines.append(
            "`required_packages` roots from manifests/hummingbird-desktops.yaml"
        )
        lines.append(
            "against the published index — the table that decides which"
        )
        lines.append("desktops tunaOS can wire (tunaOS#1755).")
        lines.append("")
        lines.append("| desktop | roots present | missing |")
        lines.append("|---|---|---|")
        for desktop, data in report["hummingbird_desktops"].items():
            missing = ", ".join(data["missing"][:6])
            if len(data["missing"]) > 6:
                missing += f", … ({len(data['missing'])} total)"
            lines.append(
                f"| {desktop} | {data['present']}/{data['roots']} "
                f"| {missing or '—'} |"
            )
        lines.append("")
    if report["unmeasured_targets"]:
        lines.append("## Not yet measured")
        lines.append("")
        lines.append(
            "These targets are NOT covered above — absence of a row is not"
        )
        lines.append("absence of a gap:")
        lines.append("")
        lines.append("| target | format | catalog entries | why |")
        lines.append("|---|---|---|---|")
        for target_id, data in sorted(report["unmeasured_targets"].items()):
            lines.append(
                f"| {target_id} | {data['format']} | {data['catalog_entries']} "
                f"| {data['reason']} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=pathlib.Path,
                        default=ROOT / "manifests" / "catalog.yaml")
    parser.add_argument("--factory", type=pathlib.Path,
                        default=ROOT / "manifests" / "package-factory.yaml")
    parser.add_argument("--out-md", type=pathlib.Path,
                        default=ROOT / "docs" / "FACTORY-STATUS.md")
    parser.add_argument("--out-json", type=pathlib.Path,
                        default=ROOT / "docs" / "factory-status.json")
    parser.add_argument("--cache", type=pathlib.Path,
                        default=pathlib.Path("/tmp/factory-status-cache"))
    parser.add_argument("--check-structure", action="store_true",
                        help="validate config shape without touching the network")
    args = parser.parse_args()

    catalog = load_yaml(args.catalog)
    factory = load_yaml(args.factory)

    if args.check_structure:
        measured = [t for t, spec in factory["targets"].items()
                    if spec.get("published_index")]
        for target_id in measured:
            spec = factory["targets"][target_id]
            if spec.get("format") not in ("rpm", "deb"):
                raise SystemExit(
                    f"{target_id}: published_index declared for a format "
                    "this tool cannot read yet"
                )
            for arch, declared in spec["published_index"].items():
                if arch not in spec.get("architectures", []):
                    raise SystemExit(
                        f"{target_id}: published_index arch {arch} is not in "
                        "the target's declared architectures"
                    )
                resolved = pubidx.normalise(declared)
                if not resolved:
                    raise SystemExit(
                        f"{target_id}/{arch}: published_index declared but empty"
                    )
                for url in resolved:
                    if not url.startswith(("https://", "file://")):
                        raise SystemExit(f"{target_id}/{arch}: unsupported URL {url}")
        if not measured:
            raise SystemExit("no target declares a published_index")
        print(f"structure ok: {len(measured)} measurable target(s)")
        return

    report = measure(catalog, factory, args.cache)
    measure_hummingbird_desktops(report, args.cache)
    args.out_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.out_md.write_text(render(report), encoding="utf-8")
    for target_id, arches in sorted(report["targets"].items()):
        for arch, data in sorted(arches.items()):
            print(
                f"{target_id}/{arch}: {len(data['built'])} built, "
                f"{len(data['needed'])} needed of {data['catalog_entries']}",
                file=sys.stderr,
            )
    print(f"wrote {args.out_md} and {args.out_json}", file=sys.stderr)


if __name__ == "__main__":
    main()
