-- Generated from themes/presets/default.json by scripts/build-theme.py.
-- Do not edit this generated file directly.
return {
    semantic = {
        surfaces = {
            background = "#0b0d11",
            surface = "#12161c",
            surface_variant = "#1b2028",
            surface_elevated = "#232a34",
        },
        text = {
            primary = "#f2f4f8",
            secondary = "#c2c8d2",
            muted = "#929baa",
            disabled = "#68717e",
        },
        accents = {
            primary = "#8ab4f8",
            secondary = "#9dd6c5",
            selection = "#253b59",
            focus = "#a8c7fa",
        },
        semantic = {
            success = "#8bd5a8",
            warning = "#f0c674",
            error = "#f28b82",
            info = "#8ab4f8",
        },
        borders = {
            default = "#343b46",
            subtle = "#242a33",
        },
    },
    hyprland = {
        active_border = {
            colors = { "rgba(8ab4f8ee)", "rgba(9dd6c5ee)" },
            angle = 45,
        },
        inactive_border = "rgba(343b46aa)",
        shadow = 0xee0b0d11,
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
