#!/usr/bin/env bash
# Build a Dank Material Shell UI directory that mirrors the packaged shell
# through symlinks and replaces only the files in dms/overrides.
#
# Run on every DMS start (see systemd/.../dms.service.d/overlay.conf), so
# package updates show up automatically. Each override may ship a
# <file>.upstream-sha256 with the hash of the packaged file it was based
# on; a mismatch means DMS changed that file and the override needs review.

set -euo pipefail
shopt -s dotglob nullglob

upstream="${DMS_UPSTREAM_DIR:-/usr/share/quickshell/dms}"
overrides="${DMS_OVERRIDES_DIR:-$(dirname "$(readlink -f "$0")")/../dms/overrides}"
target="${DMS_OVERLAY_DIR:-$HOME/.local/share/dms-overlay}"

if [[ ! -f "$upstream/shell.qml" ]]; then
    echo "dms-overlay: $upstream/shell.qml not found" >&2
    exit 1
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

    if [[ -f "$file.upstream-sha256" ]]; then
        expected="$(cat "$file.upstream-sha256")"
        actual="$(sha256sum "$upstream/$rel" 2>/dev/null | cut -d' ' -f1)"

        if [[ "$expected" != "$actual" ]]; then
            echo "dms-overlay: WARNING $rel changed upstream; review the override" >&2
        fi
    fi
done < <(find "$overrides" -type f -name '*.qml' -print0 2>/dev/null)

rm -rf "$target"
mv "$build" "$target"
