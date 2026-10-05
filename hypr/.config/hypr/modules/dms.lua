-----------------------------
---- DANK MATERIAL SHELL ----
-----------------------------

-- Integration with DMS (Quickshell-based shell). DMS regenerates the
-- files in ~/.config/hypr/dms/ itself (colors from the wallpaper, etc.),
-- so they are not part of the dotfiles and are loaded only if present.

local mainMod = "SUPER"

local function optional_require(name)
    local ok, err = pcall(require, name)

    -- Only a missing file is ignored; real errors still surface.
    if not ok and not tostring(err):find("module '" .. name .. "' not found", 1, true) then
        error(err)
    end
end

-- Wallpaper-derived colors are projected through the validated semantic
-- theme contract. When no valid dynamic module exists, appearance.lua keeps
-- the Graphite Slate static fallback.
optional_require("dms.dotfiles_theme")

-- DMS surfaces handle their own animations.
hl.layer_rule({ match = { namespace = "^(quickshell)$" }, no_anim = true })
hl.layer_rule({ match = { namespace = "^dms:.*" }, no_anim = true })

local function dms(command)
    return hl.dsp.exec_cmd("dms ipc call " .. command)
end

--------------------------------------------------
-- KEYBINDS
--------------------------------------------------

-- Only binds that do not collide with modules/keybinds.lua.

hl.bind(mainMod .. " + TAB", dms("hypr toggleOverview"))
hl.bind(mainMod .. " + O", dms("hypr toggleOverview"))

hl.bind(mainMod .. " + space", dms("spotlight toggle"))
hl.bind("ALT + space", dms("spotlight-bar toggle"))
hl.bind(mainMod .. " + comma", dms("settings focusOrToggle"))
hl.bind(mainMod .. " + N", dms("notifications toggle"))
hl.bind(mainMod .. " + SHIFT + N", dms("notepad toggle"))
hl.bind(mainMod .. " + Y", dms("dash toggle wallpaper"))
hl.bind(mainMod .. " + X", dms("powermenu toggle"))
hl.bind(mainMod .. " + SHIFT + Slash", dms("keybinds toggle hyprland"))

hl.bind(mainMod .. " + ALT + L", dms("lock lock"))
hl.bind("CTRL + ALT + Delete", dms("processlist focusOrToggle"))

hl.bind("Print", hl.dsp.exec_cmd("dms screenshot"))
hl.bind("CTRL + Print", hl.dsp.exec_cmd("dms screenshot full"))
hl.bind("ALT + Print", hl.dsp.exec_cmd("dms screenshot window"))

--------------------------------------------------
-- OVERVIEW COMMANDS
--------------------------------------------------

-- Entry points for the DMS overview (dms/overrides), which calls them as
-- Lua dispatches. The graph logic stays in WorkspaceGraph; the overview
-- cannot read return values, so refused operations become a notification
-- and the graph is left untouched.
local function report(ok, err)
    if not ok and err then
        hl.notification.create({ text = "Workspace graph: " .. err, timeout = 3000 })
    end

    return ok
end

WorkspaceOverview = {
    activate = function(id)
        return report(WorkspaceGraph.activate(id))
    end,

    -- Connects to an existing workspace, or to a new one when `to` is nil.
    connect = function(from, direction, to)
        if to == nil then
            local id, err = WorkspaceGraph.create_neighbor(from, direction)
            return report(id ~= nil, err)
        end

        return report(WorkspaceGraph.connect(from, direction, to))
    end,

    disconnect = function(from, direction)
        return report(WorkspaceGraph.disconnect(from, direction))
    end,

    create = function()
        return WorkspaceGraph.create()
    end,

    remove = function(id)
        return report(WorkspaceGraph.remove(id))
    end,
}

-- Workspace names and icons (modules/workspace_metadata.lua).
WorkspaceOverview.rename = function(id, name)
    return report(WorkspaceMetadata.set_name(id, name))
end

WorkspaceOverview.set_icon = function(id, icon)
    return report(WorkspaceMetadata.set_icon(id, icon))
end
