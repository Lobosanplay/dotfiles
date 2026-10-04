#!/usr/bin/env bash
# Build a Dank Material Shell UI directory that mirrors the packaged shell
# through symlinks and replaces only the files in dms/overrides.
#
# Run on every DMS start (see systemd/.../dms.service.d/overlay.conf), so
# package updates show up automatically. Each override of a packaged file
# ships <file>.upstream, an exact copy of the DMS file it was based on.
# If DMS changed any of those files, the overrides may no longer fit the
# new DMS: the overlay is not built, the script exits with 3 and the
# service starts the stock DMS UI until the overrides are reviewed.
#
# Usage:
#   dms-overlay.sh                     build the overlay (exit 3: review needed)
#   dms-overlay.sh --check             show which overrides need review, with
#                                      the upstream diff
#   dms-overlay.sh --update-base FILE  mark FILE (e.g.
#                                      Modules/WorkspaceOverlays/OverviewWidget.qml)
#                                      as reviewed against the installed DMS

set -euo pipefail
shopt -s dotglob nullglob

upstream="${DMS_UPSTREAM_DIR:-/usr/share/quickshell/dms}"
overrides="${DMS_OVERRIDES_DIR:-$(dirname "$(readlink -f "$0")")/../dms/overrides}"
target="${DMS_OVERLAY_DIR:-$HOME/.local/share/dms-overlay}"

if [[ ! -f "$upstream/shell.qml" ]]; then
    echo "dms-overlay: $upstream/shell.qml not found" >&2
    exit 1
fi

dms_version="$(cat "$upstream/VERSION" 2>/dev/null || echo "?")"
base_version="$(cat "$overrides/UPSTREAM_VERSION" 2>/dev/null || echo "?")"

# Overrides whose packaged file differs from the copy they were based on.
changed_overrides() {
    local base rel

    while IFS= read -r -d '' base; do
        rel="${base#"$overrides"/}"
        rel="${rel%.upstream}"

        if ! cmp -s "$base" "$upstream/$rel"; then
            echo "$rel"
        fi
    done < <(find "$overrides" -type f -name '*.upstream' -print0 2>/dev/null | sort -z)
}

case "${1:-}" in
    --check)
        changed="$(changed_overrides)"
        echo "DMS instalado: $dms_version, overrides basados en: $base_version"

        if [[ -z "$changed" ]]; then
            echo "Todos los overrides coinciden con DMS: la overlay está activa."
            exit 0
        fi

        while IFS= read -r rel; do
            echo
            echo "== $rel cambió en DMS (diff de la base a la versión instalada):"
            diff -u --label "base $base_version" --label "DMS $dms_version" \
                "$overrides/$rel.upstream" "$upstream/$rel" || true
        done <<< "$changed"
        exit 3
        ;;
    --update-base)
        rel="${2:?usage: dms-overlay.sh --update-base FILE}"

        if [[ ! -f "$overrides/$rel.upstream" || ! -f "$upstream/$rel" ]]; then
            echo "dms-overlay: $rel is not an override of a packaged file" >&2
            exit 1
        fi

        cp "$upstream/$rel" "$overrides/$rel.upstream"
        echo "$dms_version" > "$overrides/UPSTREAM_VERSION"
        echo "dms-overlay: $rel marked as reviewed against DMS $dms_version"
        exit 0
        ;;
    "") ;;
    *)
        echo "usage: dms-overlay.sh [--check | --update-base FILE]" >&2
        exit 2
        ;;
esac

changed="$(changed_overrides)"

if [[ -n "$changed" ]]; then
    # The overrides depend on each other, so none is applied. Nothing in
    # dms/overrides is touched.
    while IFS= read -r rel; do
        echo "dms-overlay: WARNING $rel changed in DMS $dms_version (overrides based on $base_version)" >&2
    done <<< "$changed"
    echo "dms-overlay: using the stock DMS UI; review with: dms-overlay.sh --check" >&2

    if command -v hyprctl >/dev/null 2>&1; then
        hyprctl notify 2 15000 0 "DMS $dms_version cambió $(echo "$changed" | xargs -n1 basename | paste -sd, -): overview de DMS normal hasta revisar (scripts/dms-overlay.sh --check)" >/dev/null 2>&1 || true
    fi

    exit 3
fi

link_contents() {
    local src="$1" dst="$2" entry

    for entry in "$src"/*; do
        ln -s "$entry" "$dst/$(basename "$entry")"
    done
}

build="$target.tmp"
rm -rf "$build"
mkdir -p "$build"
link_contents "$upstream" "$build"

while IFS= read -r -d '' file; do
    rel="${file#"$overrides"/}"
    dir="$build"
    src="$upstream"

    # Turn each symlinked parent directory into a real one.
    IFS=/ read -ra parts <<< "$(dirname "$rel")"
    for part in "${parts[@]}"; do
        [[ "$part" == "." ]] && continue

        if [[ -L "$dir/$part" ]]; then
            rm "$dir/$part"
            mkdir "$dir/$part"
            link_contents "$src/$part" "$dir/$part"
        fi

        dir="$dir/$part"
        src="$src/$part"
    done

    rm -f "$dir/$(basename "$rel")"
    cp "$file" "$dir/"
done < <(find "$overrides" -type f \( -name '*.qml' -o -name '*.js' \) -print0 2>/dev/null)

rm -rf "$target"
mv "$build" "$target"
