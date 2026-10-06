-------------------------
---- APP MINIMUM SIZE ----
-------------------------

-- Some apps refuse to lay out below a minimum width. When a tiled slot is
-- narrower, the app keeps drawing at its minimum and Hyprland clips the
-- overflow, so the content looks cut off instead of adapting (Vesktop
-- draws a 940 px page in a 790 px slot). Hyprland does not expose a
-- client's minimum size, so the measured minimums live here; a tiled
-- window narrower than its minimum is widened by moving its split, as
-- long as the neighbors keep a usable width.

local MIN_WIDTH = {
    vesktop = 940, -- Vesktop window minimum; measured viewport >= 940 px at 790 px
    spotify = 800, -- same layout at 762 and 800 px; clipped below 800
}

-- Width left for the other windows in the row; below this, leave the
-- layout alone rather than squeezing the neighbors instead.
local NEIGHBOR_MIN = 360

local function logical_width(monitor)
    return monitor.width / monitor.scale
end

local function is_tiled(window)
    return window.mapped and not window.hidden and not window.floating and window.fullscreen == 0
end

-- Tiled windows sharing the row (vertical span) of `window` on its workspace.
local function row_neighbors(window)
    local top, bottom = window.at.y, window.at.y + window.size.y
    local count = 0

    for _, other in ipairs(hl.get_workspace_windows(window.workspace.id)) do
        if other.address ~= window.address and is_tiled(other)
            and other.at.y < bottom and other.at.y + other.size.y > top then
            count = count + 1
        end
    end

    return count
end

-- Widening only works if the minimum and every neighbor in the row fit;
-- otherwise the split would collapse a window instead.
local function fits(window, min)
    return logical_width(window.monitor) >= min + NEIGHBOR_MIN * row_neighbors(window)
end

local function enforce()
    for _, window in ipairs(hl.get_windows()) do
        local min = MIN_WIDTH[window.class]

        if min and window.monitor and window.workspace and is_tiled(window)
            and window.size.x < min and fits(window, min) then
            hl.dispatch(hl.dsp.window.resize({
                x = min,
                y = window.size.y,
                window = "address:" .. window.address,
            }))
        end
    end
end

-- Layout is recalculated after these events fire; check on the next loop
-- iteration and coalesce bursts (e.g. several windows opening at login).
local timer = nil

local function schedule()
    if timer then
        return
    end

    timer = hl.timer(function()
        timer = nil
        enforce()
    end, { timeout = 50, type = "oneshot" })
end

for _, event in ipairs({ "window.open", "window.close", "window.move_to_workspace" }) do
    hl.on(event, schedule)
end

-- Also apply to windows that already exist when the config (re)loads.
schedule()
