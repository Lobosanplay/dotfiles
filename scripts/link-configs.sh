#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
config_root="${XDG_CONFIG_HOME:-$HOME/.config}"
apps=(gtk-3.0 gtk-4.0 kitty matugen niri systemd)

mkdir -p "$config_root"

for app in "${apps[@]}"; do
    source_dir="$repo_root/.config/$app"
    app_target="$config_root/$app"
    [[ -d "$source_dir" ]] || {
        printf 'Missing source config: %s\n' "$source_dir" >&2
        exit 1
    }

    if [[ -L "$app_target" && ! -e "$app_target" ]]; then
        ln -sfn "$source_dir" "$app_target"
        printf 'Repaired dangling directory link %s -> %s\n' "$app_target" "$source_dir"
        continue
    fi
    if [[ -L "$app_target" && "$(readlink -f "$app_target")" == "$source_dir" ]]; then
        printf 'Already linked: %s\n' "$app_target"
        continue
    fi

    while IFS= read -r -d '' source; do
        relative="${source#"$repo_root/.config/"}"
        target="$config_root/$relative"
        backup="$target.before-dotfiles-link"
        mkdir -p "$(dirname "$target")"

        if [[ -e "$target" && ! -L "$target" ]]; then
            if [[ -e "$backup" || -L "$backup" ]]; then
                printf 'Backup already exists; refusing to overwrite: %s\n' "$backup" >&2
                exit 1
            fi
            mv -- "$target" "$backup"
            printf 'Backed up %s -> %s\n' "$target" "$backup"
        fi

        ln -sfn "$source" "$target"
        printf '%s -> %s\n' "$target" "$source"
    done < <(find "$source_dir" -type f -print0)
done
