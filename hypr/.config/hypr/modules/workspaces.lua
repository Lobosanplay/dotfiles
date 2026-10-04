----------------------
---- WORKSPACES ------
----------------------

local workspaces = {}

local state_dir = os.getenv("HOME") .. "/.local/state/hyprland"
local state_file = state_dir .. "/workspace-graph.json"

local opposite_direction = {
    up = "down",
    down = "up",
    left = "right",
    right = "left",
}

local valid_directions = {
    up = true,
    down = true,
    left = true,
    right = true,
}

--------------------------------------------------
-- UTILITIES
--------------------------------------------------

local function ensure_workspace(id)
    if id == nil then
        return nil
    end

    if not workspaces[id] then
        workspaces[id] = {}
    end

    return workspaces[id]
end

local function workspace_exists_in_hyprland(id)
    for _, workspace in ipairs(hl.get_workspaces()) do
        if workspace.id == id then
            return true
        end
    end

    return false
end

local function next_free_workspace_id()
    local id = 1

    while workspaces[id] or workspace_exists_in_hyprland(id) do
        id = id + 1
    end

    return id
end

--------------------------------------------------
-- PERSISTENCE
--------------------------------------------------

local function serialize_graph()
    local parts = {}

    table.insert(parts, "{")

    local first_workspace = true

    for id, node in pairs(workspaces) do
        if not first_workspace then
            table.insert(parts, ",")
        end

        first_workspace = false

        table.insert(parts, string.format("%q:{", tostring(id)))

        local first_connection = true

        for direction, target in pairs(node) do
            if valid_directions[direction] and target then
                if not first_connection then
                    table.insert(parts, ",")
                end

                first_connection = false

                table.insert(
                    parts,
                    string.format("%q:%d", direction, target)
                )
            end
        end

        table.insert(parts, "}")
    end

    table.insert(parts, "}")

    return table.concat(parts)
end

local function save_graph()
    os.execute("mkdir -p " .. string.format("%q", state_dir))

    local file = io.open(state_file, "w")

    if not file then
        return false
    end

    file:write(serialize_graph())
    file:close()

    return true
end

local function load_graph()
    local file = io.open(state_file, "r")

    if not file then
        return false
    end

    local content = file:read("*a")
    file:close()

    if not content or content == "" then
        return false
    end

    --------------------------------------------------
    -- Parse workspace objects
    --------------------------------------------------

    for id, connections in content:gmatch(
        '"(%d+)"%s*:%s*{(.-)}'
    ) do
        local workspace_id = tonumber(id)

        if workspace_id then
            local node = ensure_workspace(workspace_id)

            -- left
            local target = connections:match(
                '"left"%s*:%s*(%d+)'
            )

            if target then
                node.left = tonumber(target)
            end

            -- right
            target = connections:match(
                '"right"%s*:%s*(%d+)'
            )

            if target then
                node.right = tonumber(target)
            end

            -- up
            target = connections:match(
                '"up"%s*:%s*(%d+)'
            )

            if target then
                node.up = tonumber(target)
            end

            -- down
            target = connections:match(
                '"down"%s*:%s*(%d+)'
            )

            if target then
                node.down = tonumber(target)
            end
        end
    end

    return true
end

--------------------------------------------------
-- GRAPH
--------------------------------------------------

local function connect(from, direction, to)
    local opposite = opposite_direction[direction]

    if not opposite then
        return false
    end

    if not from or not to then
        return false
    end

    local from_workspace = ensure_workspace(from)
    local to_workspace = ensure_workspace(to)

    if not from_workspace or not to_workspace then
        return false
    end

    from_workspace[direction] = to
    to_workspace[opposite] = from

    save_graph()

    return true
end

--------------------------------------------------
-- REMOVAL
--------------------------------------------------

local straight_axes = {
    { "left", "right" },
    { "up", "down" },
}

-- Removes a workspace from the graph. Its neighbors lose the connection
-- to it, and two neighbors it joined in a straight line (left-right or
-- up-down) are connected to each other when both sides are free.
local function remove(id)
    local node = workspaces[id]

    if not node then
        return false
    end

    for direction, target in pairs(node) do
        local neighbor = workspaces[target]
        local opposite = opposite_direction[direction]

        if neighbor and neighbor[opposite] == id then
            neighbor[opposite] = nil
        end
    end

    workspaces[id] = nil

    for _, axis in ipairs(straight_axes) do
        local first = node[axis[1]]
        local second = node[axis[2]]

        if first and second and first ~= second
            and workspaces[first] and workspaces[second]
            and not workspaces[first][axis[2]]
            and not workspaces[second][axis[1]] then
            workspaces[first][axis[2]] = second
            workspaces[second][axis[1]] = first
        end
    end

    save_graph()

    return true
end

--------------------------------------------------
-- HYPRLAND ACTIONS
--------------------------------------------------

local function activate(id)
    if id == nil then
        return
    end

    hl.dispatch(
        hl.dsp.focus({
            workspace = tostring(id),
        })
    )
end

local function get_active_workspace()
    return hl.get_active_workspace()
end

--------------------------------------------------
-- NAVIGATION
--------------------------------------------------

local function navigate(direction)
    if not valid_directions[direction] then
        return
    end

    local current = get_active_workspace()

    if not current then
        return
    end

    local current_id = current.id

    if current_id == nil then
        return
    end

    ensure_workspace(current_id)

    local neighbor = workspaces[current_id][direction]

    if neighbor then
        activate(neighbor)
        return
    end

    local new_id = next_free_workspace_id()

    connect(current_id, direction, new_id)

    activate(new_id)
end

--------------------------------------------------
-- INITIALIZATION
--------------------------------------------------

-- Load the saved graph first.
load_graph()

-- Register workspaces that currently exist in Hyprland.
for _, workspace in ipairs(hl.get_workspaces()) do
    if workspace.id then
        ensure_workspace(workspace.id)
    end
end

--------------------------------------------------
-- AUTOMATIC REMOVAL
--------------------------------------------------

-- Hyprland destroys a workspace when it is left empty; its graph node
-- goes with it. The event only carries the expired workspace, so removed
-- ids are found by comparing with the workspaces that were alive before.
local alive = {}
local snapshot_timer = nil

local function alive_workspace_ids()
    local ids = {}

    for _, workspace in ipairs(hl.get_workspaces()) do
        if workspace.id and workspace.id > 0 then
            ids[workspace.id] = true
        end
    end

    return ids
end

hl.on("workspace.created", function()
    -- The new workspace is listed only after the event; take the snapshot
    -- on the next loop iteration.
    snapshot_timer = hl.timer(function()
        alive = alive_workspace_ids()
    end, { timeout = 1, type = "oneshot" })
end)

hl.on("workspace.removed", function()
    local now = alive_workspace_ids()

    for id in pairs(alive) do
        if not now[id] and workspaces[id] then
            remove(id)
        end
    end

    alive = now
end)

alive = alive_workspace_ids()

--------------------------------------------------
-- PUBLIC API
--------------------------------------------------

WorkspaceGraph = {
    navigate = navigate,
    activate = activate,
    connect = connect,
    remove = remove,
    get_active_workspace = get_active_workspace,

    get_workspaces = function()
        return workspaces
    end,

    save = save_graph,
}
