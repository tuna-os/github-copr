#!/usr/bin/env bash
# The consumer's question, asked of dnf: with ONLY Hummingbird's own
# repository, our published prefix and the repositories a consumer image
# enables next to them (utah-packages for GNOME), does each desktop's root
# set resolve on the Hummingbird bootc-os image?
#
# This is utah-packages' "Validate Hummingbird-only consumer transaction"
# step, verbatim in shape: `dnf --assumeno install <roots>` inside the
# pinned bootc-os image, every other repository disabled, the transaction
# summary the verdict. scripts/check-hummingbird-installability.py is the
# static half (a Requires: walk over primary.xml, no container); this is the
# half only dnf can give -- version constraints, conflicts, the base image's
# own rpmdb, which Hummingbird deliberately uses to supply part of its
# dependency set instead of its public Pulp repository.
#
# Nothing is installed (--assumeno) and nothing is published. Advisory by
# default: the report is the product until a desktop first resolves, then
# --fail-on-unresolved keeps it that way.
#
# Usage:
#   scripts/check-hummingbird-installability-container.sh [--desktop d ...]
#       [--fail-on-unresolved] [--report FILE.md]
# Requires podman and python3 (+PyYAML) on the host; runs x86_64 only, the
# arch the consumed repositories exist for.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FACTORY="${ROOT}/manifests/package-factory.yaml"
CATALOG="${ROOT}/manifests/hummingbird-desktops.yaml"
ARCH=x86_64

desktops=()
fail_on_unresolved=0
report=""
while (($#)); do
	case "$1" in
	--desktop) desktops+=("$2"); shift 2 ;;
	--fail-on-unresolved) fail_on_unresolved=1; shift ;;
	--report) report="$2"; shift 2 ;;
	*) echo "unknown argument: $1" >&2; exit 2 ;;
	esac
done
if ((${#desktops[@]} == 0)); then
	mapfile -t desktops < <(python3 "${ROOT}/scripts/hummingbird-desktop-roots.py" --list --catalog "$CATALOG")
fi

# The target contract, read once. probe_image is the bootc-os digest tunaOS
# builds from; published_index is what images read; consumed_indexes are
# oci://…@sha256 references materialised below.
read_contract() {
	python3 - "$FACTORY" "$ARCH" <<'PY'
import sys, yaml
factory, arch = yaml.safe_load(open(sys.argv[1])), sys.argv[2]
t = factory["targets"]["hummingbird"]
m = t["gap_measurement"]
print("PROBE_IMAGE=" + t["probe_image"])
print("TARGET_INDEX=" + m["target_index"].replace("$arch", arch).replace("$basearch", arch))
print("PUBLISHED_INDEX=" + t["published_index"][arch])
for c in m.get("consumed_indexes") or []:
    print(f"CONSUMED {c['id']} {c['index']}")
PY
}

PROBE_IMAGE=""; TARGET_INDEX=""; PUBLISHED_INDEX=""
declare -A consumed_ref=()
while read -r line; do
	case "$line" in
	PROBE_IMAGE=*) PROBE_IMAGE="${line#PROBE_IMAGE=}" ;;
	TARGET_INDEX=*) TARGET_INDEX="${line#TARGET_INDEX=}" ;;
	PUBLISHED_INDEX=*) PUBLISHED_INDEX="${line#PUBLISHED_INDEX=}" ;;
	CONSUMED\ *) read -r _ id ref <<<"$line"; consumed_ref["$id"]="$ref" ;;
	esac
done < <(read_contract)
[[ -n "$PROBE_IMAGE" && -n "$TARGET_INDEX" && -n "$PUBLISHED_INDEX" ]] || {
	echo "ERROR: hummingbird contract is missing probe_image / target_index / published_index" >&2
	exit 2
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/consumed"

# Materialise each consumed OCI repository: create a container from the
# digest, copy /repository out, remove it. No registry credentials: these
# are public images pinned by digest, and the digest IS the review.
for id in "${!consumed_ref[@]}"; do
	ref="${consumed_ref[$id]#oci://}"
	echo "==> materialising consumed repository ${id} from ${ref}"
	# `true` is never executed — `podman create` only records an argv — but
	# without one it refuses an image that declares no CMD or ENTRYPOINT:
	#
	#     Error: no command or entrypoint provided, and no CMD or ENTRYPOINT
	#     from image
	#
	# and exits 125 AFTER pulling the whole 500 MB (run 33656777961). A
	# repository-only image like utah-packages has no entrypoint by design:
	# it is a createrepo_c tree, not something anyone runs.
	container="$(podman create --pull=always "$ref" true)"
	# podman cp needs the host directory to exist: on the first CI run it did
	# not, and the copy died with "could not be found on the host" after the
	# 500 MB pull (run 33619237851).
	mkdir -p "$work/consumed/${id}"
	podman cp "${container}:/repository/." "$work/consumed/${id}/"
	podman rm "$container" >/dev/null
	test -f "$work/consumed/${id}/repodata/repomd.xml" || {
		echo "ERROR: ${ref} carries no /repository/repodata/repomd.xml" >&2
		exit 2
	}
done

{
	echo "[public-hummingbird-${ARCH}-rpms]"
	echo "name=public-hummingbird-${ARCH}-rpms"
	echo "baseurl=${TARGET_INDEX}"
	echo "enabled=1"
	echo "gpgcheck=0"
	echo "priority=10"
	echo "zchunk=false"
	echo
	echo "[tunaos-hummingbird]"
	echo "name=tunaos-hummingbird (published prefix)"
	echo "baseurl=${PUBLISHED_INDEX}"
	echo "enabled=1"
	# Signature checking is install-desktop.sh's job on a real build; this
	# transaction never installs anything, and a missing key must not read as
	# "unresolvable".
	echo "gpgcheck=0"
	echo "priority=11"
	for id in "${!consumed_ref[@]}"; do
		echo
		echo "[consumed-${id}]"
		echo "name=${id} (consumed, ${consumed_ref[$id]})"
		echo "baseurl=file:///consumed/${id}"
		echo "enabled=1"
		echo "gpgcheck=0"
		echo "priority=5"
	done
} >"$work/factory.repo"

# Per-desktop root lists and which consumed repos to enable for each: every
# consumed repository is enabled for every desktop (a consumer image has
# them all), which is also the honest answer to "does kde resolve next to
# utah's GNOME": name masking between them is exactly what this catches.
for d in "${desktops[@]}"; do
	python3 "${ROOT}/scripts/hummingbird-desktop-roots.py" "$d" --catalog "$CATALOG" >"$work/roots.$d"
done

cat >"$work/inside.sh" <<'INSIDE'
set -uo pipefail
cp /work/factory.repo /etc/yum.repos.d/zz-factory-check.repo
DNF=$(command -v dnf5 || command -v dnf)
enable=(--enablerepo="public-hummingbird-*" --enablerepo=tunaos-hummingbird --enablerepo="consumed-*")
overall=0
echo "| Desktop | Roots | Verdict | First line |"
echo "|---|---|---|---|"
for d in "$@"; do
	mapfile -t roots <"/work/roots.$d"
	out=$($DNF --assumeno --setopt=install_weak_deps=False --disablerepo="*" "${enable[@]}" \
		install "${roots[@]}" 2>&1) || true
	printf '%s\n' "$out" >"/work/dnf.$d.log"
	if grep -Eqi "No match for argument|nothing provides|conflicting requests|cannot install both|does not belong to a distupgrade repository|Problem" <<<"$out"; then
		verdict="❌ unresolvable"; overall=1
		first=$(grep -Eim1 "No match for argument|nothing provides|conflicting requests|cannot install both|Problem" <<<"$out" | head -c 160)
	elif grep -Eq "Transaction Summary|Nothing to do" <<<"$out"; then
		verdict="✅ resolves"; first=$(grep -Em1 "^ *(Install|Installing) " <<<"$out" | head -c 160 || true)
	else
		verdict="⚠️ no verdict"; overall=1
		first=$(tail -n1 <<<"$out" | head -c 160)
	fi
	echo "| \`$d\` | ${#roots[@]} | $verdict | ${first//|/\\|} |"
done
exit $overall
INSIDE

echo "==> ${PROBE_IMAGE}"
set +e
podman run --rm \
	-v "$work:/work:Z" \
	-v "$work/consumed:/consumed:ro,Z" \
	"$PROBE_IMAGE" bash /work/inside.sh "${desktops[@]}" | tee "$work/table.md"
rc=${PIPESTATUS[0]}
set -e

{
	echo "### Hummingbird consumer transaction (dnf --assumeno inside \`${PROBE_IMAGE##*/}\`)"
	echo
	echo "Repositories enabled: public-hummingbird, tunaos-hummingbird (\`${PUBLISHED_INDEX}\`)$(for id in "${!consumed_ref[@]}"; do printf ', consumed %s' "$id"; done)."
	echo
	cat "$work/table.md"
	for d in "${desktops[@]}"; do
		[[ -f "$work/dnf.$d.log" ]] || continue
		if grep -q "resolves" <<<"$(grep "\`$d\`" "$work/table.md" || true)"; then continue; fi
		echo
		echo "<details><summary>dnf output for ${d} (first 60 lines)</summary>"
		echo
		echo '```'
		head -n 60 "$work/dnf.$d.log"
		echo '```'
		echo "</details>"
	done
} >"${report:-/dev/stdout}"
[[ -n "$report" ]] && echo "wrote $report"

if ((fail_on_unresolved)) && ((rc != 0)); then
	exit 1
fi
exit 0
