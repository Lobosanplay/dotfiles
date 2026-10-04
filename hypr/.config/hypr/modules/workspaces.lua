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

-- Fixed order for deterministic iteration and JSON output.
local direction_order = { "left", "right", "up", "down" }

-- Used in messages shown to the user.
local direction_names = {
    left = "la izquierda",
    right = "la derecha",
    up = "arriba",
    down = "abajo",
}

--------------------------------------------------
-- UTILITIES
--------------------------------------------------

-- Graph invariants (checked on load and kept by every edit):
--   * node ids are positive integers;
--   * links are bidirectional: a[d] == b  <=>  b[opposite(d)] == a;
--   * no self links and at most one link between two workspaces;
--   * every link points to an existing node.
-- A node may exist without a Hyprland workspace ("virtual" node): created
-- with create(), or persisted from an earlier session.

local function is_valid_id(id)
    return math.type(id) == "integer" and id > 0
end

local function ensure_workspace(id)
    if not is_valid_id(id) then
        return nil
    end

    if not workspaces[id] then
        workspaces[id] = {}
    end

    return workspaces[id]
end

local function alive_workspace_ids()
    local ids = {}

    for _, workspace in ipairs(hl.get_workspaces()) do
        if workspace.id and workspace.id > 0 then
            ids[workspace.id] = true
        end
    end

    return ids
end

local function workspace_exists_in_hyprland(id)
    return alive_workspace_ids()[id] == true
end

-- Smallest positive id that is neither a graph node nor a Hyprland
-- workspace. Removed nodes leave no references behind, so reusing their
-- ids is safe.
local function next_free_workspace_id()
    local alive = alive_workspace_ids()
    local id = 1

    while workspaces[id] or alive[id] do
        id = id + 1
    end

    return id
end

-- True if a and b are already connected in any direction.
local function linked(a, b)
    for _, target in pairs(workspaces[a] or {}) do
        if target == b then
            return true
        end
    end

    return false
end

--------------------------------------------------
-- PERSISTENCE
--------------------------------------------------

local function serialize_graph()
    local ids = {}

    for id in pairs(workspaces) do
        table.insert(ids, id)
    end

    table.sort(ids)

    local node_parts = {}

    for _, id in ipairs(ids) do
        local link_parts = {}

        for _, direction in ipairs(direction_order) do
            local target = workspaces[id][direction]

            if target then
                table.insert(
                    link_parts,
                    string.format("%q:%d", direction, target)
                )
            end
        end

        table.insert(
            node_parts,
            string.format("%q:{%s}", tostring(id), table.concat(link_parts, ","))
        )
    end

    return "{" .. table.concat(node_parts, ",") .. "}"
end

local function save_graph()
    os.execute("mkdir -p " .. string.format("%q", state_dir))

    local temp_file = state_file .. ".tmp"
    local file = io.open(temp_file, "w")

    if not file then
        return false
    end

    file:write(serialize_graph())
    file:close()

    -- Replace the file in one step so readers (the DMS overview) never see
    -- a half-written graph.
    return os.rename(temp_file, state_file) == true
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
        -- ensure_workspace rejects invalid ids such as 0.
        local node = ensure_workspace(math.tointeger(tonumber(id)))

        if node then
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

-- Returns a list of invariant violations. With `fix`, repairs them:
-- self links, links to missing nodes and duplicate links between two
-- workspaces are dropped; a one-sided link is completed when the other
-- end is free and dropped otherwise.
local function check_graph(fix)
    local problems = {}
    local ids = {}

    for id in pairs(workspaces) do
        table.insert(ids, id)
    end

    table.sort(ids)

    for _, id in ipairs(ids) do
        local node = workspaces[id]

        if not is_valid_id(id) then
            table.insert(problems, string.format("invalid id %s", tostring(id)))

            if fix then
                workspaces[id] = nil
            end
        else
            local seen = {}

            for _, direction in ipairs(direction_order) do
                local target = node[direction]
                local opposite = opposite_direction[direction]
                local other = target and workspaces[target]
                local problem = nil

                if target == nil then
                    -- no link
                elseif target == id then
                    problem = "self link"
                elseif not other then
                    problem = "link to missing node " .. tostring(target)
                elseif seen[target] then
                    problem = "second link to " .. tostring(target)
                elseif other[opposite] ~= id then
                    problem = "one-sided link to " .. tostring(target)

                    if fix and other[opposite] == nil then
                        other[opposite] = id
                        problem = problem .. " (completed)"
                    end
                end

                if problem then
                    table.insert(problems, string.format("%d.%s: %s", id, direction, problem))

                    if fix and not problem:find("completed", 1, true) then
                        node[direction] = nil

                        if other and other[opposite] == id then
                            other[opposite] = nil
                        end
                    end
                end

                if node[direction] then
                    seen[node[direction]] = true
                end
            end
        end
    end

    return problems
end

--------------------------------------------------
-- GRAPH
--------------------------------------------------

-- Connects `from` to `to` in `direction` (and `to` to `from` in the
-- opposite one). Refuses instead of overwriting: both slots must be free
-- and the workspaces must be different and not linked already. A Hyprland
-- workspace that is not in the graph yet is added. Returns ok, error.
local function connect(from, direction, to)
    local opposite = opposite_direction[direction]

    if not opposite then
        return false, "dirección no válida"
    end

    if not is_valid_id(from) or not is_valid_id(to) then
        return false, "id de workspace no válido"
    end

    if from == to then
        return false, "un workspace no puede conectarse consigo mismo"
    end

    for _, id in ipairs({ from, to }) do
        if not workspaces[id] and not workspace_exists_in_hyprland(id) then
            return false, string.format("el workspace %d no existe", id)
        end
    end

    if (workspaces[from] or {})[direction] then
        return false, string.format(
            "%d ya tiene una conexión hacia %s", from, direction_names[direction]
        )
    end

    if (workspaces[to] or {})[opposite] then
        return false, string.format(
            "%d ya tiene una conexión hacia %s", to, direction_names[opposite]
        )
    end

    if linked(from, to) then
        return false, string.format("%d y %d ya están conectados", from, to)
    end

    ensure_workspace(from)[direction] = to
    ensure_workspace(to)[opposite] = from

    save_graph()

    return true
end

-- Removes the connection of `from` in `direction`, on both ends.
-- Returns ok, error_or_former_neighbor.
local function disconnect(from, direction)
    local opposite = opposite_direction[direction]

    if not opposite then
        return false, "dirección no válida"
    end

    local node = workspaces[from]
    local to = node and node[direction]

    if not to then
        return false, string.format(
            "%s no tiene conexión hacia %s", tostring(from), direction_names[direction]
        )
    end

    node[direction] = nil

    if workspaces[to] and workspaces[to][opposite] == from then
        workspaces[to][opposite] = nil
    end

    save_graph()

    return true, to
end

-- Creates a virtual node with the smallest free id and returns it. The
-- workspace is not activated; Hyprland creates it when it is first used.
local function create()
    local id = next_free_workspace_id()

    ensure_workspace(id)
    save_graph()

    return id
end

--------------------------------------------------
-- REMOVAL
--------------------------------------------------

local straight_axes = {
    { "left", "right" },
    { "up", "down" },
}

-- Removes a node and every reference to it. Two neighbors it joined in a
-- straight line (left-right or up-down) are connected to each other when
-- both sides are free and they are not linked already.
local function remove_node(id)
    local node = workspaces[id]

    if not node then
        return false
    end

    workspaces[id] = nil

    for _, other in pairs(workspaces) do
        for _, direction in ipairs(direction_order) do
            if other[direction] == id then
                other[direction] = nil
            end
        end
    end

    for _, axis in ipairs(straight_axes) do
        local first = node[axis[1]]
        local second = node[axis[2]]

        if first and second and first ~= second
            and workspaces[first] and workspaces[second]
            and not workspaces[first][axis[2]]
            and not workspaces[second][axis[1]]
            and not linked(first, second) then
            workspaces[first][axis[2]] = second
            workspaces[second][axis[1]] = first
        end
    end

    save_graph()

    return true
end

-- Manual removal. Only virtual nodes can go: a workspace that Hyprland
-- still has (it has windows or is shown on a monitor) is removed
-- automatically once it is left empty. The last node is kept.
local function remove(id)
    if not workspaces[id] then
        return false, string.format("el workspace %s no está en el grafo", tostring(id))
    end

    if workspace_exists_in_hyprland(id) then
        return false, string.format(
            "el workspace %d está abierto; se borra solo al quedar vacío", id
        )
    end

    if next(workspaces, next(workspaces)) == nil then
        return false, "no se puede borrar el último workspace del grafo"
    end

    return remove_node(id)
end

--------------------------------------------------
-- HYPRLAND ACTIONS
--------------------------------------------------

local function activate(id)
    if not is_valid_id(id) then
        return false, "id de workspace no válido"
    end

    hl.dispatch(
        hl.dsp.focus({
            workspace = tostring(id),
        })
    )

    return true
end

local function get_active_workspace()
    return hl.get_active_workspace()
end

--------------------------------------------------
-- NAVIGATION
--------------------------------------------------

-- Creates a virtual node connected to `from` in `direction` and returns
-- its id, or nil, error when that slot is taken.
local function create_neighbor(from, direction)
    if not opposite_direction[direction] then
        return nil, "dirección no válida"
    end

    if not is_valid_id(from)
        or (not workspaces[from] and not workspace_exists_in_hyprland(from)) then
        return nil, string.format("el workspace %s no existe", tostring(from))
    end

    if (workspaces[from] or {})[direction] then
        return nil, string.format(
            "%d ya tiene una conexión hacia %s", from, direction_names[direction]
        )
    end

    local id = create()
    local ok, err = connect(from, direction, id)

    if not ok then
        remove_node(id)
        return nil, err
    end

    return id
end

-- Activates the neighbor in `direction`, creating it when there is none.
local function navigate(direction)
    if not valid_directions[direction] then
        return
    end

    local current = get_active_workspace()

    if not current or not is_valid_id(current.id) then
        return
    end

    local neighbor = (workspaces[current.id] or {})[direction]

    if neighbor then
        activate(neighbor)
        return
    end

    local new_id = create_neighbor(current.id, direction)

    if new_id then
        activate(new_id)
    end
end

-- Copy of a node's connections, or nil if it is not in the graph.
local function get_neighbors(id)
    local node = workspaces[id]

    if not node then
        return nil
    end

    local neighbors = {}

    for direction, target in pairs(node) do
        neighbors[direction] = target
    end

    return neighbors
end

--------------------------------------------------
-- INITIALIZATION
--------------------------------------------------

-- Load the saved graph first and repair anything that breaks the
-- invariants (for example a file written by an older version).
load_graph()

local repaired = #check_graph(true) > 0

-- Register regular workspaces that currently exist in Hyprland.
for id in pairs(alive_workspace_ids()) do
    if not workspaces[id] then
        ensure_workspace(id)
        repaired = true
    end
end

if repaired then
    save_graph()
end

--------------------------------------------------
-- AUTOMATIC REMOVAL
--------------------------------------------------

-- Hyprland destroys a workspace when it is left empty; its graph node
-- goes with it. The event only carries the expired workspace, so removed
-- ids are found by comparing with the workspaces that were alive before.
local alive = {}
local snapshot_timer = nil

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
            remove_node(id)
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
    disconnect = disconnect,
    create = create,
    create_neighbor = create_neighbor,
    remove = remove,
    get_neighbors = get_neighbors,
    get_active_workspace = get_active_workspace,

    -- The live table; read it, change it only through the functions above.
    get_workspaces = function()
        return workspaces
    end,

    -- Returns ok, problems: the invariant violations found (none expected).
    validate = function()
        local problems = check_graph(false)
        return #problems == 0, problems
    end,

    save = save_graph,
}
