-- Generated from themes/presets/default.json by scripts/build-theme.py.
-- Do not edit this generated file directly.
return {
    semantic = {
        surfaces = {
            background = "#0d0f12",
            surface = "#14171b",
            surface_variant = "#1d2126",
            surface_elevated = "#272c32",
        },
        text = {
            primary = "#e6e8eb",
            secondary = "#c0c4ca",
            muted = "#9298a1",
            disabled = "#6d737c",
        },
        accents = {
            primary = "#aab4c0",
            secondary = "#929ca8",
            selection = "#303943",
            focus = "#c2c8d0",
        },
        semantic = {
            success = "#a5bca9",
            warning = "#c5b995",
            error = "#c59d9d",
            info = "#aab4c0",
        },
        borders = {
            default = "#3b4149",
            subtle = "#292e34",
        },
    },
    hyprland = {
        active_border = {
            colors = { "rgba(aab4c0ee)", "rgba(929ca8ee)" },
            angle = 45,
        },
        inactive_border = "rgba(3b4149aa)",
        shadow = 0xee0d0f12,
    },
    typography = {
        families = {
            ui = {
                primary = "Inter Variable",
                source = "DMS-bundled",
                fallback = {
                    "Adwaita Sans",
                    "Noto Sans",
                    "sans-serif",
                },
            },
            mono = {
                primary = "FiraCode Nerd Font",
                source = "DMS-bundled",
                fallback = {
                    "Adwaita Mono",
                    "Noto Sans Mono",
                    "monospace",
                },
            },
        },
        scale_unit = "logical-px",
        scale = {
            display = 32,
            title = 20,
            heading = 16,
            body = 14,
            label = 12,
            caption = 11,
            micro = 10,
        },
        weights = {
            regular = 400,
            medium = 500,
            semibold = 600,
            bold = 700,
        },
        line_height = {
            compact = 1.2,
            normal = 1.4,
            relaxed = 1.55,
        },
    },
    iconography = {
        provider = "material-symbols-rounded",
        family = "Material Symbols Rounded",
        source = "DMS-bundled",
        symbol_format = "lowercase-ligature-name",
        api = {
            ["DankIcon.name"] = "<ligature-name>",
            ["AppIconRenderer.iconValue"] = "material:<ligature-name>",
        },
        aliases = {
            close = "close",
            settings = "settings",
            workspace = "grid_view",
            terminal = "terminal",
            code = "code",
            browser = "web",
            music = "music_note",
        },
        fallback = "system-icon-theme-for-application-and-file-icons",
    },
}
