------------------
---- MONITORS ----
------------------

hl.monitor({
    output   = "eDP-1",
    mode     = "1920x1200@180",
    position = "0x0",
    -- 1.25 leaves a 1536x960 logical desktop, wide enough for the desktop
    -- layouts of web pages and Electron apps (1.5 left only 1280x800).
    scale    = 1.25,
})

hl.monitor({
    output   = "HDMI-A-2",
    mode     = "1600x900@60",
    position = "1536x0", -- right of eDP-1's logical width
    scale    = 1,
})

-- XWayland apps (Minecraft, Java, X11) are drawn at scale 1 and upscaled on
-- eDP-1. Filter that upscale instead of nearest-neighbor, which looks
-- pixelated at a fractional scale.
hl.config({
    xwayland = {
        use_nearest_neighbor = false,
    },
})
