-------------------
---- AUTOSTART ----
-------------------

-- Apps launched once when Hyprland starts, each sent to its workspace
-- without changing focus. Hyprland does not run ~/.config/autostart
-- (xdg-desktop-autostart.target is never started in this session).
--
-- Exec rules match by PID, which does not survive the Flatpak sandbox,
-- and window rules would also move windows opened later by hand. Instead,
-- windows of these classes are moved once each while the startup window
-- below is open: Vesktop maps a splash window before its main window, so
-- the class stays armed until the timer ends. Classes are compared in
-- lowercase because Spotify sets its class after the window maps (hence
-- also "window.class").

local APPS = {
    { class = "vesktop", workspace = 2, cmd = "flatpak run dev.vencord.Vesktop" },
    { class = "spotify", workspace = 2, cmd = "flatpak run com.spotify.Client" },
}

-- Seconds after start during which windows of these classes are moved.
local STARTUP_WINDOW = 120

local pending = {}
local moved = {}

local function place_pending()
    for _, window in ipairs(hl.get_windows()) do
        local class = window.class and window.class:lower()
        local app = class and pending[class]

        if app and window.mapped and not moved[window.address] then
            moved[window.address] = true
            hl.dispatch(hl.dsp.window.move({
                workspace = app.workspace,
                follow = false,
                window = "address:" .. window.address,
            }))
        end
    end
end

for _, event in ipairs({ "window.open", "window.class" }) do
    hl.on(event, function()
        if next(pending) then
            place_pending()
        end
    end)
end

hl.on("hyprland.start", function()
    for _, app in ipairs(APPS) do
        pending[app.class] = app
        hl.exec_cmd(app.cmd)
    end

    hl.timer(function()
        pending = {}
        moved = {}
    end, { timeout = STARTUP_WINDOW * 1000, type = "oneshot" })
end)
