# My Linux Dotfiles

Personal Linux desktop configuration.

## Current setup

- Fedora Linux
- niri
- Wayland
- Intel integrated graphics
- NVIDIA RTX 3050 Laptop GPU
- Kitty
- Dwindle layout

## Structure

```text
dotfiles/
├── .config/
│   ├── gtk-3.0/
│   ├── gtk-4.0/
│   ├── kitty/
│   ├── matugen/
│   ├── niri/
│   └── systemd/
├── dms/
├── scripts/
├── tests/
├── themes/
├── wallpapers/
└── README.md
```

Link managed configuration files with `scripts/link-configs.sh`. Existing
regular files are preserved as `*.before-dotfiles-link`; generated or unrelated
files in the same application directories are left untouched.
