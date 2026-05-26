from __future__ import annotations

import random
from dataclasses import dataclass

from .battle_types import TerrainCell, TerrainType


@dataclass(frozen=True)
class TerrainProperties:
    mp_cost: int
    cover_bonus: float
    blocks_los: bool
    concealment: float
    label_cn: str


TERRAIN_PROPS: dict[TerrainType, TerrainProperties] = {
    TerrainType.OPEN: TerrainProperties(mp_cost=2, cover_bonus=0.0, blocks_los=False, concealment=0.0, label_cn="开阔"),
    TerrainType.ROAD: TerrainProperties(mp_cost=1, cover_bonus=0.0, blocks_los=False, concealment=0.0, label_cn="道路"),
    TerrainType.FOREST: TerrainProperties(mp_cost=4, cover_bonus=0.25, blocks_los=False, concealment=0.30, label_cn="森林"),
    TerrainType.URBAN: TerrainProperties(mp_cost=3, cover_bonus=0.40, blocks_los=True, concealment=0.40, label_cn="城区"),
    TerrainType.WATER: TerrainProperties(mp_cost=5, cover_bonus=0.0, blocks_los=False, concealment=0.0, label_cn="水域"),
    TerrainType.ROUGH: TerrainProperties(mp_cost=5, cover_bonus=0.15, blocks_los=False, concealment=0.10, label_cn="崎岖"),
    TerrainType.MARSH: TerrainProperties(mp_cost=6, cover_bonus=0.10, blocks_los=False, concealment=0.15, label_cn="沼泽"),
    TerrainType.MOUNTAIN: TerrainProperties(mp_cost=6, cover_bonus=0.35, blocks_los=True, concealment=0.20, label_cn="山地"),
}

ROLE_TERRAIN_BONUS: dict[str, dict[TerrainType, int]] = {
    "scout": {TerrainType.FOREST: -2, TerrainType.MOUNTAIN: -1},
    "assaulter": {TerrainType.WATER: -3, TerrainType.MARSH: -2},
    "attacker": {TerrainType.ROAD: -1},
    "defender": {TerrainType.URBAN: -1, TerrainType.ROUGH: -2},
    "support": {TerrainType.ROAD: -2},
    "coordinator": {TerrainType.MOUNTAIN: -1},
}


def cost_for(terrain_type: TerrainType, role_key: str | None = None) -> int:
    base = TERRAIN_PROPS[terrain_type].mp_cost
    bonus_map = ROLE_TERRAIN_BONUS.get(role_key or "", {})
    bonus = bonus_map.get(terrain_type, 0)
    return max(1, base + bonus)


def cover_for(terrain_type: TerrainType) -> float:
    return TERRAIN_PROPS[terrain_type].cover_bonus


def blocks_los(terrain_type: TerrainType) -> bool:
    return TERRAIN_PROPS[terrain_type].blocks_los


def concealment_for(terrain_type: TerrainType) -> float:
    return TERRAIN_PROPS[terrain_type].concealment


def terrain_label(terrain_type: TerrainType) -> str:
    return TERRAIN_PROPS[terrain_type].label_cn


def generate_plains_terrain(width: int, height: int) -> list[list[TerrainCell]]:
    grid = [[TerrainCell(TerrainType.OPEN) for _ in range(width)] for _ in range(height)]
    mid_y = height // 2 - 1 + random.randint(0, 1)
    for x in range(width):
        grid[mid_y][x] = TerrainCell(TerrainType.ROAD)
    forest_clusters = max(2, width * height // 20)
    for _ in range(forest_clusters):
        cx = random.randint(1, width - 2)
        cy = random.randint(0, height - 1)
        if cy == mid_y:
            continue
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < width and 0 <= ny < height and ny != mid_y:
                    grid[ny][nx] = TerrainCell(TerrainType.FOREST)
    return grid


def generate_jungle_terrain(width: int, height: int) -> list[list[TerrainCell]]:
    grid = [[TerrainCell(TerrainType.FOREST) for _ in range(width)] for _ in range(height)]
    river_y = height // 2 - 1 + random.randint(0, 1)
    for x in range(width):
        grid[river_y][x] = TerrainCell(TerrainType.WATER)
    if river_y + 1 < height:
        for x in range(width):
            if random.random() < 0.6:
                grid[river_y + 1][x] = TerrainCell(TerrainType.MARSH)
    if river_y - 1 >= 0:
        for x in range(width):
            if random.random() < 0.4:
                grid[river_y - 1][x] = TerrainCell(TerrainType.MARSH)
    open_clearings = max(2, width * height // 16)
    for _ in range(open_clearings):
        cx = random.randint(0, width - 1)
        cy = random.randint(0, height - 1)
        if abs(cy - river_y) <= 1:
            continue
        grid[cy][cx] = TerrainCell(TerrainType.OPEN)
    for y in range(height):
        for x in range(width):
            if grid[y][x].type == TerrainType.FOREST and random.random() < 0.15 and abs(y - river_y) > 1:
                grid[y][x] = TerrainCell(TerrainType.ROUGH)
    return grid


def generate_urban_terrain(width: int, height: int) -> list[list[TerrainCell]]:
    grid = [[TerrainCell(TerrainType.OPEN) for _ in range(width)] for _ in range(height)]
    urban_w = max(4, width // 2)
    urban_h = max(3, height // 2)
    ux = (width - urban_w) // 2
    uy = (height - urban_h) // 2
    for y in range(uy, uy + urban_h):
        for x in range(ux, ux + urban_w):
            grid[y][x] = TerrainCell(TerrainType.URBAN)
    for y in range(height):
        for x in range(width):
            mid_cx = width // 2 - 1 + random.randint(0, 1)
            mid_cy = height // 2 - 1 + random.randint(0, 1)
            if grid[y][x].type == TerrainType.OPEN and (x == mid_cx or y == mid_cy):
                grid[y][x] = TerrainCell(TerrainType.ROAD)
    for y in range(uy - 1, uy + urban_h + 1):
        for x in range(ux - 1, ux + urban_w + 1):
            if 0 <= x < width and 0 <= y < height and grid[y][x].type == TerrainType.OPEN:
                if random.random() < 0.3:
                    grid[y][x] = TerrainCell(TerrainType.ROAD)
    return grid


TERRAIN_PRESETS: dict[str, tuple[str, str]] = {
    "plains": ("开阔平原", "以开阔地为主，对角线道路贯穿，两侧点缀树丛"),
    "jungle": ("丛林地带", "密集森林+水域河流+沼泽低洼，隐蔽性强"),
    "urban": ("城市战区", "中央城区建筑群，道路放射状连接，周边开阔"),
}

TERRAIN_GENERATORS: dict[str, callable] = {
    "plains": generate_plains_terrain,
    "jungle": generate_jungle_terrain,
    "urban": generate_urban_terrain,
}


def generate_terrain(preset: str, width: int, height: int) -> list[list[TerrainCell]]:
    gen = TERRAIN_GENERATORS.get(preset)
    if gen:
        return gen(width, height)
    return generate_plains_terrain(width, height)
