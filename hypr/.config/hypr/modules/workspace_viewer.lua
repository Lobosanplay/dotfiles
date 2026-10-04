----------------------------
---- WORKSPACE VIEWER ------
----------------------------

-- Visual overlay for the workspace graph defined in workspaces.lua.
-- This module only reads WorkspaceGraph; it never modifies the graph.

local viewer_script = os.getenv("HOME") .. "/dotfiles/scripts/workspace-viewer.py"

-- The bracket keeps pkill from matching the shell that runs it.
local viewer_pattern = "[w]orkspace-viewer\\.py"

local directions = { "left", "right", "up", "down" }

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

    if active and active.id then
        active_json = string.format("%d", active.id)
    end

    return string.format(
        '{"active":%s,"workspaces":{%s}}',
        active_json,
        table.concat(node_parts, ",")
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
        "pkill -e -f '" .. viewer_pattern .. "' 2>/dev/null"
    )

    if not pipe then
        return false
    end

    local output = pipe:read("a")
    pipe:close()

    return output ~= nil and output ~= ""
end

local function open()
    -- The JSON only contains digits, braces and quoted direction names,
    -- so single quotes are safe here.
    hl.exec_cmd(
        "python3 '" .. viewer_script .. "' '" .. build_state_json() .. "'"
    )
end

local function toggle()
    if not close() then
        open()
    end
end

--------------------------------------------------
-- PUBLIC API
--------------------------------------------------

WorkspaceViewer = {
    open = open,
    close = close,
    toggle = toggle,
}
