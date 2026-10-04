-------------------------------
---- WORKSPACE METADATA -------
-------------------------------

-- Optional name and icon per workspace graph node, kept apart from the
-- graph in ~/.local/state/hyprland/workspace-metadata.json:
--   {"3": {"name": "code", "icon": "terminal"}}
-- Icons are Material Symbols names (the icon font bundled with DMS).
-- Entries follow the graph: they are dropped when their node is removed,
-- so a reused id never inherits an old name.

local metadata = {}

local state_dir = os.getenv("HOME") .. "/.local/state/hyprland"
local state_file = state_dir .. "/workspace-metadata.json"

local MAX_NAME = 32
local MAX_ICON = 48

--------------------------------------------------
-- VALIDATION
--------------------------------------------------

-- Names never contain quotes, backslashes or control characters, so the
-- JSON can be written and read without escaping.
local function valid_name(name)
    return type(name) == "string" and #name <= MAX_NAME
        and not name:find('[%c"\\]')
end

local function valid_icon(icon)
    return type(icon) == "string" and #icon <= MAX_ICON
        and icon:match("^[a-z0-9_]+$") ~= nil
end

local function trim(text)
    return (text or ""):match("^%s*(.-)%s*$")
end

local function in_graph(id)
    return WorkspaceGraph.get_workspaces()[id] ~= nil
end

--------------------------------------------------
-- PERSISTENCE
--------------------------------------------------

local function save()
    local ids = {}

    for id in pairs(metadata) do
        table.insert(ids, id)
    end

    table.sort(ids)

    local parts = {}

    for _, id in ipairs(ids) do
        local fields = {}

        for _, key in ipairs({ "name", "icon" }) do
            if metadata[id][key] then
                table.insert(fields, string.format('"%s":"%s"', key, metadata[id][key]))
            end
        end

        table.insert(parts, string.format('"%d":{%s}', id, table.concat(fields, ",")))
    end

    os.execute("mkdir -p " .. string.format("%q", state_dir))

    local temp_file = state_file .. ".tmp"
    local file = io.open(temp_file, "w")

    if not file then
        return false
    end

    file:write("{" .. table.concat(parts, ",") .. "}")
    file:close()

    return os.rename(temp_file, state_file) == true
end

-- Loads entries that are valid and belong to a graph node; anything else
-- is dropped (and the file rewritten).
local function load()
    local file = io.open(state_file, "r")

    if not file then
        return
    end

    local content = file:read("a")
    file:close()

    local dropped = false

    for id, body in content:gmatch('"(%d+)"%s*:%s*{(.-)}') do
        id = math.tointeger(tonumber(id))

        local name = body:match('"name"%s*:%s*"([^"]*)"')
        local icon = body:match('"icon"%s*:%s*"([^"]*)"')
        local entry = {
            name = valid_name(name) and name ~= "" and name or nil,
            icon = valid_icon(icon) and icon or nil,
        }

        if id and in_graph(id) and (entry.name or entry.icon) then
            metadata[id] = entry
        else
            dropped = true
        end
    end

    if dropped then
        save()
    end
end

--------------------------------------------------
-- API
--------------------------------------------------

local function set_field(id, key, value, valid, message)
    if not in_graph(id) then
        return false, string.format("el workspace %s no está en el grafo", tostring(id))
    end

    value = trim(value)

    if value ~= "" and not valid(value) then
        return false, message
    end

    local entry = metadata[id] or {}
    entry[key] = value ~= "" and value or nil
    metadata[id] = (entry.name or entry.icon) and entry or nil

    save()

    return true
end

local function clear(id)
    if metadata[id] then
        metadata[id] = nil
        save()
    end

    return true
end

WorkspaceGraph.on_removed(clear)

load()

WorkspaceMetadata = {
    -- Copy of {name, icon} for a workspace, or nil.
    get = function(id)
        local entry = metadata[id]
        return entry and { name = entry.name, icon = entry.icon } or nil
    end,

    -- Empty or nil clears the field. Returns ok, error.
    set_name = function(id, name)
        return set_field(id, "name", name, valid_name, string.format(
            "nombre no válido (máx. %d caracteres, sin comillas ni barras invertidas)", MAX_NAME
        ))
    end,

    set_icon = function(id, icon)
        return set_field(id, "icon", icon, valid_icon,
            "icono no válido: usa un nombre de Material Symbols (a-z, 0-9, _)")
    end,

    clear = clear,
}
