----------------------------
---- WORKSPACE VIEWER ------
----------------------------

-- Visual overlay for the workspace graph defined in workspaces.lua.
-- This module only reads WorkspaceGraph; it never modifies the graph.

local viewer_script = os.getenv("HOME") .. "/dotfiles/scripts/workspace-viewer.py"

-- Anchored to the interpreter so pkill only matches viewer processes,
-- never an editor or shell that merely mentions the script's path.
local viewer_pattern = "^[^ ]*python[0-9.]* [^ ]*/workspace-viewer\\.py( |$)"

local directions = { "left", "right", "up", "down" }

--------------------------------------------------
-- JSON / SHELL HELPERS
--------------------------------------------------

-- Window titles can contain anything, so strings are escaped properly.
local function json_string(value)
    local escaped = tostring(value):gsub('[%c"\\]', function(char)
        if char == '"' or char == "\\" then
            return "\\" .. char
        end

        return string.format("\\u%04x", char:byte())
    end)

    return '"' .. escaped .. '"'
end

local function shell_quote(value)
    return "'" .. value:gsub("'", "'\\''") .. "'"
end

local function round(value)
    return math.floor(value + 0.5)
end

--------------------------------------------------
-- DATA
--------------------------------------------------

-- Collect every known workspace: graph nodes plus regular workspaces
-- that currently exist in Hyprland but were never connected.
local function collect_nodes()
    local nodes = {}

    for id, connections in pairs(WorkspaceGraph.get_workspaces()) do
        nodes[id] = connections
    end

    for _, workspace in ipairs(hl.get_workspaces()) do
        if workspace.id and workspace.id > 0 and not workspace.special then
            nodes[workspace.id] = nodes[workspace.id] or {}
        end
    end

    return nodes
end

-- Snapshot used to draw workspace previews: the logical frame of each
-- monitor, which monitor shows each workspace, and the mapped windows.
-- Window positions stay global; the viewer subtracts the monitor origin.
local function build_preview_json()
    local monitor_parts = {}

    for _, monitor in ipairs(hl.get_monitors()) do
        -- width/height are physical pixels; positions are logical.
        local width = monitor.width / monitor.scale
        local height = monitor.height / monitor.scale

        if monitor.transform and monitor.transform % 2 == 1 then
            width, height = height, width
        end

        table.insert(monitor_parts, string.format(
            "%s:[%d,%d,%d,%d]",
            json_string(monitor.name),
            round(monitor.x), round(monitor.y), round(width), round(height)
        ))
    end

    local workspace_monitor_parts = {}

    for _, workspace in ipairs(hl.get_workspaces()) do
        if workspace.id and workspace.id > 0 and workspace.monitor then
            table.insert(workspace_monitor_parts, string.format(
                '"%d":%s',
                workspace.id,
                json_string(workspace.monitor.name)
            ))
        end
    end

    local client_parts = {}

    for _, window in ipairs(hl.get_windows()) do
        local workspace = window.workspace

        if window.mapped and not window.hidden
            and workspace and workspace.id and workspace.id > 0 then
            table.insert(client_parts, string.format(
                '{"workspace":%d,"at":[%d,%d],"size":[%d,%d],'
                    .. '"class":%s,"title":%s,"floating":%s,'
                    .. '"fullscreen":%s,"focus":%d}',
                workspace.id,
                round(window.at.x), round(window.at.y),
                round(window.size.x), round(window.size.y),
                json_string(window.class or ""),
                json_string(window.title or ""),
                tostring(window.floating == true),
                tostring((window.fullscreen or 0) ~= 0),
                window.focus_history_id or 0
            ))
        end
    end

    return string.format(
        '"monitors":{%s},"workspace_monitors":{%s},"clients":[%s]',
        table.concat(monitor_parts, ","),
        table.concat(workspace_monitor_parts, ","),
        table.concat(client_parts, ",")
    )
end

local function build_state_json()
    local nodes = collect_nodes()
    local node_parts = {}

    for id, connections in pairs(nodes) do
        local edge_parts = {}

        for _, direction in ipairs(directions) do
            local target = connections[direction]

            if target then
                table.insert(
                    edge_parts,
                    string.format("%q:%d", direction, target)
                )
            end
        end

        table.insert(
            node_parts,
            string.format("%q:{%s}", tostring(id), table.concat(edge_parts, ","))
        )
    end

    local active = WorkspaceGraph.get_active_workspace()
    local active_json = "null"
    local monitor_json = "null"

    if active and active.id then
        active_json = string.format("%d", active.id)
    end

    -- The viewer opens on the monitor that shows the active workspace.
    if active and active.monitor and active.monitor.name then
        monitor_json = json_string(active.monitor.name)
    end

    return string.format(
        '{"active":%s,"monitor":%s,"workspaces":{%s},%s}',
        active_json,
        monitor_json,
        table.concat(node_parts, ","),
        build_preview_json()
    )
end

--------------------------------------------------
-- PROCESS CONTROL
--------------------------------------------------

-- Returns true if a running viewer was found and closed.
--
-- Hyprland reaps child processes itself, so os.execute() cannot report
-- exit codes here. Instead, pkill -e prints one line per killed process.
local function close()
    local pipe = io.popen(
        "pkill -e -f " .. shell_quote(viewer_pattern) .. " 2>/dev/null"
    )

    if not pipe then
        return false
    end

    local output = pipe:read("a")
    pipe:close()

    return output ~= nil and output ~= ""
end

local function open()
    hl.exec_cmd(
        "python3 " .. shell_quote(viewer_script)
            .. " " .. shell_quote(build_state_json())
    )
end

local function toggle()
    if not close() then
        open()
    end
end

-- Called by the viewer process (via hyprctl dispatch) when the user
-- confirms a selection. Activation itself belongs to WorkspaceGraph.
local function activate(id)
    WorkspaceGraph.activate(tonumber(id))
end

--------------------------------------------------
-- PUBLIC API
--------------------------------------------------

WorkspaceViewer = {
    open = open,
    close = close,
    toggle = toggle,
    activate = activate,
}
