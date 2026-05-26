from __future__ import annotations

from .battle_types import Position, TerrainType, TerrainCell

GridType = str


def normalize_grid_type(grid_type: str | None) -> GridType:
    return "hex" if grid_type == "hex" else "square"


def oddr_to_axial(pos: Position) -> tuple[int, int]:
    q = pos.x - (pos.y - (pos.y & 1)) // 2
    r = pos.y
    return q, r


def distance(a: Position, b: Position, grid_type: str | None = "square") -> int:
    if normalize_grid_type(grid_type) != "hex":
        return a.distance_to(b)
    aq, ar = oddr_to_axial(a)
    bq, br = oddr_to_axial(b)
    return int((abs(aq - bq) + abs(aq + ar - bq - br) + abs(ar - br)) / 2)


def neighbors(pos: Position, grid_type: str | None = "square") -> list[Position]:
    if normalize_grid_type(grid_type) != "hex":
        offsets = ((1, 0), (-1, 0), (0, 1), (0, -1))
    elif pos.y & 1:
        offsets = ((1, 0), (-1, 0), (0, 1), (1, 1), (0, -1), (1, -1))
    else:
        offsets = ((1, 0), (-1, 0), (-1, 1), (0, 1), (-1, -1), (0, -1))
    return [Position(pos.x + dx, pos.y + dy) for dx, dy in offsets]


def cells_in_radius(center: Position, radius: int, width: int, height: int, grid_type: str | None = "square") -> list[Position]:
    result: list[Position] = []
    for y in range(height):
        for x in range(width):
            pos = Position(x, y)
            if distance(center, pos, grid_type) <= radius:
                result.append(pos)
    return result


def _resolve_terrain_type(cell: object) -> TerrainType:
    if isinstance(cell, TerrainCell):
        return cell.type
    if isinstance(cell, TerrainType):
        return cell
    return TerrainType.OPEN


def _terrain_cost_at(pos: Position, terrain_grid: list[list] | None) -> int:
    if terrain_grid and 0 <= pos.y < len(terrain_grid) and 0 <= pos.x < len(terrain_grid[pos.y]):
        tt = _resolve_terrain_type(terrain_grid[pos.y][pos.x])
        from .terrain import cost_for
        return cost_for(tt)
    return 2


def reachable_cells(
    source: Position,
    movement_points: int,
    width: int,
    height: int,
    grid_type: str = "square",
    terrain_grid: list[list] | None = None,
    occupied: set[Position] | None = None,
) -> dict[Position, int]:
    result: dict[Position, int] = {}
    visited: dict[Position, int] = {source: movement_points}
    queue: list[Position] = [source]
    occupied_set = occupied or set()

    while queue:
        current = queue.pop(0)
        remaining = visited[current]
        for nxt in neighbors(current, grid_type):
            if nxt.x < 0 or nxt.x >= width or nxt.y < 0 or nxt.y >= height:
                continue
            if nxt in occupied_set and nxt != source:
                continue
            cost = _terrain_cost_at(nxt, terrain_grid)
            new_remaining = remaining - cost
            if new_remaining < 0:
                continue
            if nxt not in visited or visited[nxt] < new_remaining:
                visited[nxt] = new_remaining
                result[nxt] = new_remaining
                queue.append(nxt)
    return result


def step_toward(
    source: Position,
    target: Position,
    width: int,
    height: int,
    grid_type: str | None = "square",
    steps: int = 1,
    terrain_grid: list[list] | None = None,
    movement_points: int = 0,
) -> Position:
    if movement_points > 0 and terrain_grid:
        return step_toward_weighted(source, target, width, height, terrain_grid, movement_points)
    return step_toward_unweighted(source, target, width, height, grid_type, steps)


def step_toward_unweighted(
    source: Position,
    target: Position,
    width: int,
    height: int,
    grid_type: str | None = "square",
    steps: int = 1,
) -> Position:
    current = Position(source.x, source.y)
    for _ in range(max(1, steps)):
        candidates = [
            item
            for item in neighbors(current, grid_type)
            if 0 <= item.x < width and 0 <= item.y < height
        ]
        if not candidates:
            return current
        best = min(candidates, key=lambda item: distance(item, target, grid_type))
        if distance(best, target, grid_type) >= distance(current, target, grid_type):
            return current
        current = best
    return current


def step_toward_weighted(
    source: Position,
    target: Position,
    width: int,
    height: int,
    terrain_grid: list[list] | None = None,
    movement_points: int = 6,
) -> Position:
    from .terrain import cost_for as terrain_cost

    def safe_cost(p: Position) -> int:
        if terrain_grid and 0 <= p.y < len(terrain_grid) and 0 <= p.x < len(terrain_grid[p.y]):
            return terrain_cost(_resolve_terrain_type(terrain_grid[p.y][p.x]))
        return 2

    open_set = {source}
    came_from: dict[Position, Position | None] = {source: None}
    g_score: dict[Position, float] = {source: 0}
    f_score: dict[Position, float] = {source: distance(source, target, "hex")}
    while open_set:
        current = min(open_set, key=lambda p: f_score.get(p, float("inf")))
        if current == target or distance(current, target, "hex") <= 1:
            path = []
            while current is not None and current in came_from:
                path.append(current)
                current = came_from[current]
            path.reverse()
            if len(path) <= 1:
                return source
            next_step = path[1]
            total_cost = sum(safe_cost(p) for p in path[1:])
            if total_cost > movement_points:
                return source
            return next_step
        open_set.remove(current)
        for nxt in neighbors(current, "hex"):
            if nxt.x < 0 or nxt.x >= width or nxt.y < 0 or nxt.y >= height:
                continue
            move_cost = safe_cost(nxt)
            tentative = g_score.get(current, float("inf")) + move_cost
            if tentative > movement_points:
                continue
            if tentative < g_score.get(nxt, float("inf")):
                came_from[nxt] = current
                g_score[nxt] = tentative
                f_score[nxt] = tentative + distance(nxt, target, "hex")
                open_set.add(nxt)
    return source


def has_line_of_sight(
    from_pos: Position,
    to_pos: Position,
    terrain_grid: list[list] | None = None,
) -> bool:
    if terrain_grid is None:
        return True
    x0, y0 = from_pos.x, from_pos.y
    x1, y1 = to_pos.x, to_pos.y
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        if (x, y) != (x0, y0) and (x, y) != (x1, y1):
            if 0 <= y < len(terrain_grid) and 0 <= x < len(terrain_grid[y]):
                from .terrain import blocks_los
                if blocks_los(_resolve_terrain_type(terrain_grid[y][x])):
                    return False
        if x == x1 and y == y1:
            break
        e2 = err * 2
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return True
