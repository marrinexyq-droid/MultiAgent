<template>
  <section class="hex-map-card">
    <div class="hex-map-head">
      <div class="hex-map-head-left">
        <span class="hex-round-pill">ROUND {{ frame?.turn ?? 0 }}</span>
        <span class="hex-hud-divider"></span>
        <span class="hex-hud-grid">{{ frame?.map.width ?? 0 }} × {{ frame?.map.height ?? 0 }} HEX</span>
        <span class="hex-hud-divider"></span>
        <span class="hex-hud-stat"><span class="hud-red">●</span> {{ redAlive }}/{{ redTotal }}</span>
        <span class="hex-hud-stat"><span class="hud-blue">●</span> {{ blueAlive }}/{{ blueTotal }}</span>
      </div>
      <div class="hex-hud-stat" v-if="frame">
        <span class="hud-gold">●</span> {{ alivePct }}% 存活
      </div>
    </div>

    <template v-if="frame">
      <div class="hex-board-scroll" ref="boardScrollRef" @mousedown="onDragStart" @mousemove="onDragMove" @mouseup="onDragEnd" @mouseleave="onDragEnd" @wheel.prevent="onWheel">
        <div class="hex-hud-scanlines"></div>
        <div class="hex-hud-corner hex-hud-tl"></div>
        <div class="hex-hud-corner hex-hud-tr"></div>
        <div class="hex-hud-corner hex-hud-bl"></div>
        <div class="hex-hud-corner hex-hud-br"></div>
        <div class="hex-hud-data hex-hud-data-tl">SAT-LINK ▼ ONLINE</div>
        <div class="hex-hud-data hex-hud-data-tr">GRID {{ frame?.map.width }}×{{ frame?.map.height }}</div>
        <div class="hex-hud-data hex-hud-data-bl">UPLINK: STABLE</div>
        <div class="hex-hud-data hex-hud-data-br">T+ {{ frame?.turn ?? 0 }}s</div>
        <div class="hex-board" :style="{ ...boardStyle, transform: `scale(${zoom})`, transformOrigin: '0 0' }">
          <button
            v-for="cell in renderedCells"
            :key="`${cell.x}-${cell.y}`"
            type="button"
            class="hex-cell"
            :class="cell.classes"
            :style="cell.style"
            :aria-label="cellAria(cell)"
            :disabled="cell.fogDark"
            @click="handleCellClick(cell)"
            @mouseenter="hoveredPos = { x: cell.x, y: cell.y }"
            @mouseleave="hoveredPos = null"
            @focusin="hoveredPos = { x: cell.x, y: cell.y }"
            @focusout="hoveredPos = null"
          >
          <!-- Layer 1: 3D SVG Terrain -->
          <HexTerrainIcon v-if="!cell.fogDark" :type="cell.terrainType" :x="cell.x" :y="cell.y" />

            <!-- Layer 2: Zone overlays -->
            <div v-if="cell.fogDark" class="hex-zone-overlay zone-fog-dark"></div>
            <div v-else-if="cell.fogExplored" class="hex-zone-overlay zone-fog-explored"></div>
            <template v-else>
              <div v-if="cell.redSpawn && !cell.showUnit" class="hex-zone-overlay zone-red-spawn"></div>
              <div v-if="cell.blueSpawn && !cell.showUnit" class="hex-zone-overlay zone-blue-spawn"></div>
              <div v-if="cell.control" class="hex-zone-overlay zone-control"></div>
              <div v-if="cell.contested" class="hex-zone-overlay zone-contested"></div>
              <div v-if="cell.inRange" class="hex-zone-overlay zone-range"></div>
              <div v-if="cell.inAttackRange" class="hex-zone-overlay zone-attack-range"></div>
            </template>
            <!-- Cell coordinates -->
            <span v-if="!cell.fogDark" class="hex-cell-coord">{{ cell.x }},{{ cell.y }}</span>
            <!-- Resource marker -->
            <span v-if="cell.resource" class="hex-resource-marker">{{ cell.resource }}</span>

            <!-- Layer 3: Unit badge -->
          <div v-if="cell.showUnit" class="hex-unit-badge" :class="[`team-${cell.unit.team}`, { focused: cell.unit.agent_id === focusedAgentId }]" :style="{ '--role-color': cell.roleColor }">
            <div class="badge-team-bar" :style="{ background: cell.roleColor }"></div>
            <div v-if="cell.hasCover" class="badge-cover-shield">🛡</div>
            <div v-if="cell.stateIcon" class="badge-status-icon">{{ cell.stateIcon }}</div>
            <div class="badge-body">
              <div class="badge-top-row">
                <span class="badge-role-icon">{{ cell.roleIcon }}</span>
                <span class="badge-role-label">{{ cell.roleLabel }}</span>
                <div class="badge-hp-track">
                  <div class="badge-hp-fill" :style="{ width: cell.hpPct + '%' }"></div>
                </div>
              </div>
              <div class="badge-bottom-row">
                <span class="badge-id">{{ cell.unit.team === "red" ? "R" : "B" }}{{ cell.unitIndex }}</span>
                <span v-if="cell.stateLabel" class="badge-state-tag" :class="cell.stateTagClass">{{ cell.stateLabel }}</span>
              </div>
            </div>
          </div>

            <!-- Tooltip -->
            <div v-if="showTooltip(cell)" class="hex-terrain-tooltip">
              <strong>{{ terrainLabel(cell.terrainType) }}</strong>
              <span>({{ cell.x }},{{ cell.y }}) · {{ terrainDesc(cell.terrainType) }}</span>
            </div>
          </button>

          <svg class="hex-effect-layer" :width="boardWidth" :height="boardHeight" :viewBox="`0 0 ${boardWidth} ${boardHeight}`">
            <circle v-for="effect in effectCircles" :key="effect.key" :cx="effect.cx" :cy="effect.cy" :r="effect.r" :class="`hex-effect-circle ${effect.type}`" />
          </svg>

          <div class="hex-dmg-layer">
            <HexDamageNumber v-for="dmg in dmgNumbers" :key="dmg.key" :x="dmg.x" :y="dmg.y" :value="dmg.value" :type="dmg.type" />
          </div>
          <svg class="hex-intent-layer" :width="boardWidth" :height="boardHeight" :viewBox="`0 0 ${boardWidth} ${boardHeight}`">
            <line v-for="line in intentLines" :key="line.key" :x1="line.x1" :y1="line.y1" :x2="line.x2" :y2="line.y2" :class="`intent-line intent-${line.type}`" />
            <circle v-for="dot in intentLineDots" :key="dot.key" :cx="dot.cx" :cy="dot.cy" r="4" :class="`intent-dot intent-${dot.type}`" />
            <line v-for="tl in threatLines" :key="tl.key" :x1="tl.x1" :y1="tl.y1" :x2="tl.x2" :y2="tl.y2" class="threat-line" />
            <g v-if="focusCircles.length"><circle v-for="c in focusCircles" :key="c.key" :cx="c.cx" :cy="c.cy" :r="c.r" :class="`inf-circle inf-${c.type} focus-highlight`" /></g>
            <g v-if="showInfluence"><circle v-for="inf in influenceCircles" :key="inf.key" :cx="inf.cx" :cy="inf.cy" :r="inf.r" :class="`inf-circle inf-${inf.type}`" /></g>
            <g v-if="showDiffs">
              <line v-for="d in diffMoves" :key="d.key" :x1="d.x1" :y1="d.y1" :x2="d.x2" :y2="d.y2" class="diff-move-arrow" :style="{ stroke: d.team === 'red' ? '#ef4444' : '#3b82f6' }" />
              <text v-for="d in diffHp" :key="d.key" :x="d.cx" :y="d.cy" :class="`diff-hp-text diff-hp-${d.dir}`">{{ d.label }}</text>
            </g>
          </svg>
          <svg class="hex-skill-layer" :width="boardWidth" :height="boardHeight" :viewBox="`0 0 ${boardWidth} ${boardHeight}`">
            <line v-for="s in skillLines" :key="s.key" :x1="s.x1" :y1="s.y1" :x2="s.x2" :y2="s.y2" :class="`skill-line skill-${s.type}`" />
            <circle v-for="c in skillImpacts" :key="c.key" :cx="c.cx" :cy="c.cy" :r="5" :class="`impact-circle impact-${c.type}`" />
            <g v-for="x in deathCrosses" :key="x.key">
              <line :x1="x.x1" :y1="x.y1" :x2="x.x2" :y2="x.y2" class="death-cross" />
              <line :x1="x.x2" :y1="x.y1" :x2="x.x1" :y2="x.y2" class="death-cross" />
            </g>
          </svg>
        </div>
      </div>

      <canvas v-if="frame" class="hex-minimap" ref="minimapRef" :width="minimapW" :height="minimapH" @click="onMinimapClick"></canvas>

      <div v-if="timelineMarkers && timelineMarkers.length" class="hex-map-timeline">
        <div class="hex-timeline-bar-compact">
          <button v-for="m in timelineMarkers" :key="m.id" type="button" class="hex-timeline-dot" :class="`tl-${m.type.toLowerCase()}`" :title="`T${m.turn} ${m.label}: ${m.summary}`" :style="{ left: m.pct + '%' }" @click="$emit('jump', m)"></button>
        </div>
      </div>
    </template>

    <div v-else class="empty-state">创建 Hex Lab 演练后，这里会显示六边形沙盘。</div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { BattleFrame, RoleKey } from "../types";
import HexTerrainIcon from "./HexTerrainIcon.vue";
import HexDamageNumber from "./HexDamageNumber.vue";

const props = defineProps<{
  frame: BattleFrame | null;
  focusedAgentId: string;
  selectedTeam?: string;
  previousFrame?: BattleFrame | null;
  showDiffs?: boolean;
  showInfluence?: boolean;
  focusedUnitInfo?: { vision: number; attack: number; pos: { x: number; y: number } } | null;
  timelineMarkers?: Array<{ id: string; turn: number; type: string; pct: number; label: string; summary: string }>;
}>();

const emit = defineEmits<{
  "focus-agent": [agentId: string];
  jump: [marker: { turn: number; actor_id?: string | null; target_id?: string | null }];
}>();

const redAlive = computed(() => props.frame?.units.filter((u) => u.team === "red" && u.alive).length ?? 0);
const redTotal = computed(() => props.frame?.units.filter((u) => u.team === "red").length ?? 0);
const blueAlive = computed(() => props.frame?.units.filter((u) => u.team === "blue" && u.alive).length ?? 0);
const blueTotal = computed(() => props.frame?.units.filter((u) => u.team === "blue").length ?? 0);
const alivePct = computed(() => {
  const t = redTotal.value + blueTotal.value;
  const a = redAlive.value + blueAlive.value;
  return t > 0 ? Math.round((a / t) * 100) : 0;
});

const boardScrollRef = ref<HTMLElement | null>(null);
const minimapRef = ref<HTMLCanvasElement | null>(null);
const hoveredPos = ref<{ x: number; y: number } | null>(null);
const showRange = ref(false);
const rangeCells = ref<Set<string>>(new Set());
const exploredCells = ref<Set<string>>(new Set());
const zoom = ref(1);
const minimapW = 120;
const minimapH = 90;
let isDragging = false;
let dragStart = { x: 0, y: 0 };
let scrollStart = { left: 0, top: 0 };

function onDragStart(e: MouseEvent) {
  isDragging = true;
  dragStart = { x: e.clientX, y: e.clientY };
  if (boardScrollRef.value) {
    scrollStart = { left: boardScrollRef.value.scrollLeft, top: boardScrollRef.value.scrollTop };
  }
}
function onDragMove(e: MouseEvent) {
  if (!isDragging || !boardScrollRef.value) return;
  boardScrollRef.value.scrollLeft = scrollStart.left - (e.clientX - dragStart.x);
  boardScrollRef.value.scrollTop = scrollStart.top - (e.clientY - dragStart.y);
}
function onDragEnd() { isDragging = false; }
function onWheel(e: WheelEvent) {
  const delta = e.deltaY > 0 ? -0.1 : 0.1;
  zoom.value = Math.max(0.4, Math.min(2, zoom.value + delta));
}

watch(() => props.frame, (frame) => {
  if (frame) drawMinimap(frame);
  if (!frame || props.selectedTeam === "all" || !frame.map.visibility) return;
  const vis = frame.map.visibility[props.selectedTeam as "red" | "blue"];
  if (!vis) return;
  for (let y = 0; y < frame.map.height; y++) {
    for (let x = 0; x < frame.map.width; x++) {
      if (vis[y]?.[x]) {
        exploredCells.value.add(`${x},${y}`);
      }
    }
  }
});

const hexWidth = 78;
const hexHeight = 88;
const rowStep = hexHeight * 0.75;
const boardPad = 34;

const boardWidth = computed(() => {
  const w = props.frame?.map.width ?? 0;
  return boardPad * 2 + w * hexWidth + hexWidth / 2;
});
const boardHeight = computed(() => {
  const h = props.frame?.map.height ?? 0;
  return boardPad * 2 + Math.max(1, h) * rowStep + hexHeight - rowStep;
});
const boardStyle = computed(() => ({
  width: `${boardWidth.value}px`,
  height: `${boardHeight.value}px`,
}));

const TERRAIN_LABELS: Record<string, string> = {
  open: "开阔", road: "道路", forest: "森林", urban: "城区",
  water: "水域", rough: "崎岖", marsh: "沼泽", mountain: "山地",
};
const TERRAIN_COST: Record<string, number> = {
  open: 2, road: 1, forest: 4, urban: 3,
  water: 5, rough: 5, marsh: 6, mountain: 6,
};
const TERRAIN_COVER: Record<string, string> = {
  open: "无", road: "无", forest: "25%", urban: "40%",
  water: "无", rough: "15%", marsh: "10%", mountain: "35%",
};

function terrainLabel(t: string): string { return TERRAIN_LABELS[t] ?? t; }
function terrainDesc(t: string): string {
  return `成本${TERRAIN_COST[t] ?? 2}MP 掩护${TERRAIN_COVER[t] ?? "无"}`;
}

function getTerrainType(x: number, y: number): string {
  const frame = props.frame;
  if (!frame?.map.terrain) return "open";
  return frame.map.terrain[y]?.[x]?.type ?? "open";
}

function hexOffsets(x: number, y: number): Array<[number, number]> {
  if (y & 1) return [[1,0],[-1,0],[0,1],[1,1],[0,-1],[1,-1]];
  return [[1,0],[-1,0],[-1,1],[0,1],[-1,-1],[0,-1]];
}

function hexDist(a: { x: number; y: number }, b: { x: number; y: number }): number {
  const aq = a.x - Math.floor((a.y - (a.y & 1)) / 2);
  const bq = b.x - Math.floor((b.y - (b.y & 1)) / 2);
  const ar = a.y, br = b.y;
  return (Math.abs(aq - bq) + Math.abs(aq + ar - bq - br) + Math.abs(ar - br)) / 2;
}

function inZoneList(zones: BattleFrame["map"]["control_zones"], x: number, y: number) {
  return zones.some((z) => x >= z.x && x < z.x + z.width && y >= z.y && y < z.y + z.height);
}

function computeReachableCells(agentId: string): Set<string> {
  const frame = props.frame;
  if (!frame) return new Set();
  const unit = frame.units.find((u) => u.agent_id === agentId);
  if (!unit || !unit.alive) return new Set();
  const mp = unit.movement_points || unit.move_speed * 3;
  const result = new Set<string>();
  const visited = new Map<string, number>();
  const queue: Array<{ x: number; y: number; rem: number }> = [{ x: unit.pos.x, y: unit.pos.y, rem: mp }];
  const key = (a: number, b: number) => `${a},${b}`;
  visited.set(key(unit.pos.x, unit.pos.y), mp);
  while (queue.length) {
    const cur = queue.shift()!;
    const rem = visited.get(key(cur.x, cur.y)) ?? 0;
    for (const [dx, dy] of hexOffsets(cur.x, cur.y)) {
      const nx = cur.x + dx, ny = cur.y + dy;
      const nk = key(nx, ny);
      if (nx < 0 || nx >= frame.map.width || ny < 0 || ny >= frame.map.height) continue;
      const cost = TERRAIN_COST[getTerrainType(nx, ny)] ?? 2;
      const nr = rem - cost;
      if (nr < 0) continue;
      const prev = visited.get(nk);
      if (prev === undefined || prev < nr) { visited.set(nk, nr); result.add(nk); queue.push({ x: nx, y: ny, rem: nr }); }
    }
  }
  return result;
}

function computeContestedCells(): Set<string> {
  const frame = props.frame;
  if (!frame) return new Set();
  const redPos = frame.units.filter((u) => u.alive && u.team === "red").map((u) => u.pos);
  const bluePos = frame.units.filter((u) => u.alive && u.team === "blue").map((u) => u.pos);
  const result = new Set<string>();
  for (let y = 0; y < frame.map.height; y++) {
    for (let x = 0; x < frame.map.width; x++) {
      const hasRedNear = redPos.some((p) => hexDist(p, { x, y }) <= 1);
      const hasBlueNear = bluePos.some((p) => hexDist(p, { x, y }) <= 1);
      if (hasRedNear && hasBlueNear) result.add(`${x},${y}`);
    }
  }
  return result;
}

const ROLE_IDENTITY: Record<RoleKey, { icon: string; code: string; label: string; color: string; statLabel: string }> = {
  coordinator: { icon: "🎯", code: "CO", label: "协调", color: "#fbbf24", statLabel: "协同" },
  scout:      { icon: "👁", code: "SC", label: "侦察", color: "#3b82f6", statLabel: "视野" },
  attacker:   { icon: "⚔", code: "AT", label: "攻击", color: "#ef4444", statLabel: "火力" },
  defender:   { icon: "🛡", code: "DF", label: "防御", color: "#22c55e", statLabel: "护甲" },
  support:    { icon: "🔧", code: "SP", label: "支援", color: "#06b6d4", statLabel: "补给" },
  jammer:     { icon: "📡", code: "JM", label: "干扰", color: "#a855f7", statLabel: "干扰" },
  controller: { icon: "🔒", code: "CT", label: "控制", color: "#f97316", statLabel: "封锁" },
  assaulter:  { icon: "💥", code: "AS", label: "突击", color: "#ec4899", statLabel: "机动" },
};

/* ── Visibility helpers ── */
function isCellVisible(x: number, y: number, team: string): boolean {
  const frame = props.frame;
  if (!frame?.map.visibility) return true;
  const grid = frame.map.visibility[team as "red" | "blue"];
  if (!grid) return false;
  const row = grid[y];
  if (!row) return false;
  return row[x] === true;
}

const COVER_TYPES = new Set(["forest", "urban", "mountain", "rough", "marsh"]);

function getRoleId(unit: Record<string, unknown>): {
  icon: string; code: string; label: string; color: string; statLabel: string
} {
  return ROLE_IDENTITY[unit.role as RoleKey] ?? { icon: "❓", code: "??", label: "未知", color: "#666", statLabel: "" };
}

function buildCellBadge(unit: Record<string, unknown>, frame: BattleFrame, terrainType: string) {
  const u = frame.units.find((u2) => u2.agent_id === unit.agent_id);
  const hpPct = u && u.max_hp ? Math.max(0, Math.round((u.hp / u.max_hp) * 100)) : 0;
  const ri = getRoleId(unit);
  const roleCode = ri.code;
  const roleLabel = ri.label;
  const roleIcon = ri.icon;
  const roleColor = ri.color;
  const unitIndex = (String(unit.agent_id).match(/_(\d+)$/)?.[1]) ?? "1";
  const hasCover = COVER_TYPES.has(terrainType);
  const flags = u?.status_flags ?? [];
  let stateDot = "";
  let stateLabel = "";
  let stateTagClass = "";
  let stateIcon = "";
  if (u && u.hp <= u.max_hp * 0.45) { stateDot = "dot-damaged"; stateLabel = "受损"; stateTagClass = "tag-damaged"; stateIcon = "💔"; }
  else if (flags.includes("jammed")) { stateDot = "dot-jammed"; stateLabel = "干扰"; stateTagClass = "tag-jammed"; stateIcon = "📡"; }
  else if (flags.includes("blocked")) { stateDot = "dot-blocked"; stateLabel = "封锁"; stateTagClass = "tag-blocked"; stateIcon = "🔒"; }
  else if (flags.includes("exposed")) { stateDot = "dot-exposed"; stateLabel = "暴露"; stateTagClass = "tag-exposed"; stateIcon = "👁"; }
  return { hpPct, roleCode, roleLabel, roleIcon, roleColor, unitIndex, stateDot, stateLabel, stateTagClass, stateIcon, hasCover };
}

const renderedCells = computed(() => {
  const frame = props.frame;
  if (!frame) return [];
  const contested = computeContestedCells();
  const selectedTeam = props.selectedTeam || "all";

  /* Compute attack range for focused unit's target */
  let attackCells = new Set<string>();
  if (showRange.value && props.focusedAgentId) {
    const fu = frame.units.find((u) => u.agent_id === props.focusedAgentId);
    if (fu && fu.alive) {
      const atkRange = fu.attack_range || 1;
      for (let ay = 0; ay < frame.map.height; ay++) {
        for (let ax = 0; ax < frame.map.width; ax++) {
          if (hexDist(fu.pos, { x: ax, y: ay }) <= atkRange) {
            attackCells.add(`${ax},${ay}`);
          }
        }
      }
    }
  }

  const cells = [];
  for (let y = 0; y < frame.map.height; y++) {
    for (let x = 0; x < frame.map.width; x++) {
      const unit = frame.map.cells[y]?.[x] ?? null;
      const tt = getTerrainType(x, y);
      const cellKey = `${x},${y}`;
      const isInRange = showRange.value && rangeCells.value.has(cellKey);
      const isInAttackRange = showRange.value && attackCells.has(cellKey);
      const isContested = contested.has(cellKey) && !unit;

      const isVisible = selectedTeam === "all" || isCellVisible(x, y, selectedTeam);
      const isExplored = exploredCells.value.has(cellKey);
      const fogDark = selectedTeam !== "all" && !isVisible && !isExplored;
      const fogExplored = selectedTeam !== "all" && !isVisible && isExplored;
      const showUnit = unit && (selectedTeam === "all" || isVisible);

      let hasEdge = false;
      for (const [dx, dy] of hexOffsets(x, y)) {
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || nx >= frame.map.width || ny < 0 || ny >= frame.map.height) continue;
        if (getTerrainType(nx, ny) !== tt) { hasEdge = true; break; }
      }
      /* Fog edge glow: visible cell next to fog */
      let fogEdge = false;
      if (selectedTeam !== "all" && isVisible) {
        for (const [dx, dy] of hexOffsets(x, y)) {
          const nx = x + dx, ny = y + dy;
          if (nx < 0 || nx >= frame.map.width || ny < 0 || ny >= frame.map.height) continue;
          if (!isCellVisible(nx, ny, selectedTeam)) { fogEdge = true; break; }
        }
      }
      /* Resource markers */
      let resource = "";
      if (!fogDark && !fogExplored) {
        const ctrl = inZoneList(frame.map.control_zones, x, y);
        if (ctrl) resource = "🎯";
      }

      const classes: Record<string, boolean> = {};
      if (isInRange) classes["in-range"] = true;
      if (hasEdge) classes["terrain-edge"] = true;
      if (fogEdge) classes["fog-edge"] = true;

      const badge = unit && showUnit ? buildCellBadge(unit, frame, tt) : null;

      cells.push({
        x, y,
        unit: showUnit ? unit : null,
        terrainType: tt,
        control: inZoneList(frame.map.control_zones, x, y) && !fogDark,
        redSpawn: inZoneList(frame.map.red_spawn_zones, x, y) && !fogDark,
        blueSpawn: inZoneList(frame.map.blue_spawn_zones, x, y) && !fogDark,
        contested: isContested && !fogDark && !fogExplored,
        inRange: isInRange,
        inAttackRange: isInAttackRange,
        resource: resource,
        fogDark, fogExplored, showUnit, classes,
        style: {
          left: `${boardPad + x * hexWidth + (y % 2 ? hexWidth / 2 : 0)}px`,
          top: `${boardPad + y * rowStep}px`,
        },
        hpPct: badge?.hpPct ?? 0,
        roleCode: badge?.roleCode ?? "",
        roleLabel: badge?.roleLabel ?? "",
        roleIcon: badge?.roleIcon ?? "",
        roleColor: badge?.roleColor ?? "",
        unitIndex: badge?.unitIndex ?? "",
        stateDot: badge?.stateDot ?? "",
        stateLabel: badge?.stateLabel ?? "",
        stateTagClass: badge?.stateTagClass ?? "",
        stateIcon: badge?.stateIcon ?? "",
        hasCover: badge?.hasCover ?? false,
      });
    }
  }
  return cells;
});

const effectCircles = computed(() => {
  const frame = props.frame;
  if (!frame) return [];
  return (frame.map.effects ?? []).map((eff, i) => {
    const c = eff.center as { x?: number; y?: number } | undefined;
    if (c?.x === undefined || c?.y === undefined) return null;
    const r = Number(eff.radius ?? 0);
    return {
      key: `${i}-${String(eff.type ?? "effect")}`,
      cx: boardPad + c.x * hexWidth + (c.y % 2 ? hexWidth / 2 : 0) + hexWidth / 2,
      cy: boardPad + c.y * rowStep + hexHeight / 2,
      r: Math.max(32, (r + 0.65) * rowStep),
      type: String(eff.type ?? "effect"),
    };
  }).filter(Boolean) as Array<{ key: string; cx: number; cy: number; r: number; type: string }>;
});

function cellCenterPx(x: number, y: number): { cx: number; cy: number } {
  return {
    cx: boardPad + x * hexWidth + (y % 2 ? hexWidth / 2 : 0) + hexWidth / 2,
    cy: boardPad + y * rowStep + hexHeight / 2,
  };
}

/* ── Intention & Threat Lines ── */
const intentLines = computed(() => {
  const frame = props.frame;
  if (!frame) return [];
  const lines: Array<{ key: string; x1: number; y1: number; x2: number; y2: number; type: string }> = [];
  const seen = new Set<string>();
  for (const ev of frame.events_structured) {
    if (!ev.target_id && !ev.target_position) continue;
    const actor = frame.units.find((u) => u.agent_id === ev.actor_id);
    if (!actor || !actor.alive) continue;
    const uid = ev.actor_id!;
    if (seen.has(uid)) continue;
    seen.add(uid);
    const from = cellCenterPx(actor.pos.x, actor.pos.y);
    if (ev.target_position) {
      const to = cellCenterPx(ev.target_position.x, ev.target_position.y);
      lines.push({ key: `${uid}-intent`, x1: from.cx, y1: from.cy, x2: to.cx, y2: to.cy, type: ev.type.toLowerCase() });
    } else if (ev.target_id) {
      const target = frame.units.find((u) => u.agent_id === ev.target_id);
      if (target) {
        const to = cellCenterPx(target.pos.x, target.pos.y);
        lines.push({ key: `${uid}-intent`, x1: from.cx, y1: from.cy, x2: to.cx, y2: to.cy, type: ev.type.toLowerCase() });
      }
    }
  }
  return lines;
});

const intentLineDots = computed(() => {
  const frame = props.frame;
  if (!frame) return [];
  const dots: Array<{ key: string; cx: number; cy: number; type: string }> = [];
  const seen = new Set<string>();
  for (const ev of frame.events_structured) {
    if (!ev.target_id && !ev.target_position) continue;
    const uid = ev.actor_id!;
    if (seen.has(uid)) continue;
    seen.add(uid);
    if (ev.target_position) {
      const to = cellCenterPx(ev.target_position.x, ev.target_position.y);
      dots.push({ key: `${uid}-dot`, cx: to.cx, cy: to.cy, type: ev.type.toLowerCase() });
    } else if (ev.target_id) {
      const target = frame.units.find((u) => u.agent_id === ev.target_id);
      if (target) {
        const to = cellCenterPx(target.pos.x, target.pos.y);
        dots.push({ key: `${uid}-dot`, cx: to.cx, cy: to.cy, type: ev.type.toLowerCase() });
      }
    }
  }
  return dots;
});

const threatLines = computed(() => {
  const frame = props.frame;
  if (!frame) return [];
  const lines: Array<{ key: string; x1: number; y1: number; x2: number; y2: number }> = [];
  for (const ev of frame.events_structured) {
    if (ev.type !== "ATTACK" || !ev.target_id) continue;
    const actor = frame.units.find((u) => u.agent_id === ev.actor_id);
    const target = frame.units.find((u) => u.agent_id === ev.target_id);
    if (!actor || !target || !actor.alive || !target.alive) continue;
    const from = cellCenterPx(actor.pos.x, actor.pos.y);
    const to = cellCenterPx(target.pos.x, target.pos.y);
    lines.push({ key: `threat-${ev.turn}-${ev.actor_id}`, x1: from.cx, y1: from.cy, x2: to.cx, y2: to.cy });
  }
  return lines;
});

/* ── Influence (zone of control) ── */
const focusCircles = computed(() => {
  const info = props.focusedUnitInfo;
  if (!info || !info.vision) return [];
  const c = cellCenterPx(info.pos.x, info.pos.y);
  const visPx = info.vision * (hexWidth * 0.7);
  const atkPx = Math.max(info.attack, 1) * (hexWidth * 0.7);
  return [
    { key: "focus-vis", cx: c.cx, cy: c.cy, r: visPx, type: "vision" },
    { key: "focus-atk", cx: c.cx, cy: c.cy, r: atkPx, type: "attack" },
  ];
});

const influenceCircles = computed(() => {
  const frame = props.frame;
  if (!frame) return [];
  const circles: Array<{ key: string; cx: number; cy: number; r: number; type: string }> = [];
  for (const u of frame.units) {
    if (!u.alive) continue;
    const center = cellCenterPx(u.pos.x, u.pos.y);
    const visPx = (u.vision_range || 3) * (hexWidth * 0.7);
    const atkPx = (u.attack_range || 1) * (hexWidth * 0.7);
    circles.push({ key: `vis-${u.agent_id}`, cx: center.cx, cy: center.cy, r: visPx, type: "vision" });
    circles.push({ key: `atk-${u.agent_id}`, cx: center.cx, cy: center.cy, r: atkPx, type: "attack" });
  }
  return circles;
});

/* ── Frame diff overlays ── */
const diffMoves = computed(() => {
  const cur = props.frame;
  const prev = props.previousFrame;
  if (!cur || !prev) return [];
  const lines: Array<{ key: string; x1: number; y1: number; x2: number; y2: number; team: string }> = [];
  for (const pu of prev.units) {
    if (!pu.alive) continue;
    const cu = cur.units.find((u) => u.agent_id === pu.agent_id);
    if (!cu || !cu.alive) continue;
    if (cu.pos.x !== pu.pos.x || cu.pos.y !== pu.pos.y) {
      const from = cellCenterPx(pu.pos.x, pu.pos.y);
      const to = cellCenterPx(cu.pos.x, cu.pos.y);
      lines.push({ key: `move-${pu.agent_id}`, x1: from.cx + 10, y1: from.cy, x2: to.cx - 10, y2: to.cy, team: pu.team });
    }
  }
  return lines;
});

/* ── Damage floating numbers ── */
const dmgNumbers = computed(() => {
  const cur = props.frame;
  const prev = props.previousFrame;
  if (!cur || !prev) return [];
  const items: Array<{ key: string; x: number; y: number; value: number; type: string }> = [];
  for (const pu of prev.units) {
    if (!pu.alive) continue;
    const cu = cur.units.find((u) => u.agent_id === pu.agent_id);
    if (!cu || !cu.alive) {
      const pos = cellCenterPx(pu.pos.x, pu.pos.y);
      items.push({ key: `dead-${pu.agent_id}`, x: pos.cx, y: pos.cy - 10, value: 0, type: "kill" });
      continue;
    }
    const diff = cu.hp - pu.hp;
    if (diff < 0) {
      const pos = cellCenterPx(cu.pos.x, cu.pos.y);
      items.push({ key: `dmg-${pu.agent_id}`, x: pos.cx, y: pos.cy - 10, value: Math.abs(diff), type: "damage" });
    } else if (diff > 0) {
      const pos = cellCenterPx(cu.pos.x, cu.pos.y);
      items.push({ key: `heal-${pu.agent_id}`, x: pos.cx, y: pos.cy - 10, value: diff, type: "heal" });
    }
  }
  return items;
});

const diffHp = computed(() => {
  const cur = props.frame;
  const prev = props.previousFrame;
  if (!cur || !prev) return [];
  const labels: Array<{ key: string; cx: number; cy: number; label: string; dir: string }> = [];
  for (const pu of prev.units) {
    if (!pu.alive) continue;
    const cu = cur.units.find((u) => u.agent_id === pu.agent_id);
    if (!cu) {
      const pos = cellCenterPx(pu.pos.x, pu.pos.y);
      labels.push({ key: `dead-${pu.agent_id}`, cx: pos.cx, cy: pos.cy - 14, label: "✕", dir: "dead" });
      continue;
    }
    if (!cu.alive) {
      const pos = cellCenterPx(cu.pos.x, cu.pos.y);
      labels.push({ key: `dead-${cu.agent_id}`, cx: pos.cx, cy: pos.cy - 14, label: "✕", dir: "dead" });
      continue;
    }
    const diff = cu.hp - pu.hp;
    if (diff !== 0) {
      const pos = cellCenterPx(cu.pos.x, cu.pos.y);
      const label = diff > 0 ? `+${diff}` : `${diff}`;
      labels.push({ key: `hp-${cu.agent_id}`, cx: pos.cx, cy: pos.cy - 14, label, dir: diff > 0 ? "up" : "down" });
    }
  }
  return labels;
});

/* ── Skill effects & projectiles ── */
const SKILL_TYPE_MAP: Record<string, string> = {
  coordination_pulse: "coordination", scan_field: "scan", focused_burst: "attack",
  guard_field: "guard", support_link: "support", link_jam: "jam",
  zone_lock: "coordination", engage_trace: "engage",
};

const skillLines = computed(() => {
  const frame = props.frame;
  if (!frame) return [];
  const lines: Array<{ key: string; x1: number; y1: number; x2: number; y2: number; type: string }> = [];
  for (const ev of frame.events_structured) {
    if (ev.type === "ATTACK" && ev.target_id) {
      const actor = frame.units.find((u) => u.agent_id === ev.actor_id);
      const target = frame.units.find((u) => u.agent_id === ev.target_id);
      if (actor && target) {
        const f = cellCenterPx(actor.pos.x, actor.pos.y);
        const t = cellCenterPx(target.pos.x, target.pos.y);
        lines.push({ key: `proj-${ev.turn}-${ev.actor_id}`, x1: f.cx, y1: f.cy, x2: t.cx, y2: t.cy, type: "attack" });
      }
    }
    if (ev.type === "ENGAGE" && ev.target_id) {
      const actor = frame.units.find((u) => u.agent_id === ev.actor_id);
      const target = frame.units.find((u) => u.agent_id === ev.target_id);
      if (actor && target) {
        const f = cellCenterPx(actor.pos.x, actor.pos.y);
        const t = cellCenterPx(target.pos.x, target.pos.y);
        lines.push({ key: `proj-${ev.turn}-${ev.actor_id}`, x1: f.cx, y1: f.cy, x2: t.cx, y2: t.cy, type: "engage" });
      }
    }
    if (ev.type === "SKILL" || ev.type === "TASK") {
      const effectKey = (ev.metadata?.effect as string) || "";
      const skillType = SKILL_TYPE_MAP[effectKey] || "coordination";
      const actor = frame.units.find((u) => u.agent_id === ev.actor_id);
      if (actor && ev.target_position) {
        const f = cellCenterPx(actor.pos.x, actor.pos.y);
        const t = cellCenterPx(ev.target_position.x, ev.target_position.y);
        lines.push({ key: `skill-${ev.turn}-${ev.actor_id}`, x1: f.cx, y1: f.cy, x2: t.cx, y2: t.cy, type: skillType });
      }
    }
  }
  return lines;
});

const skillImpacts = computed(() => {
  const frame = props.frame;
  if (!frame) return [];
  const circles: Array<{ key: string; cx: number; cy: number; type: string }> = [];
  for (const ev of frame.events_structured) {
    if (ev.type === "ATTACK" && ev.target_position) {
      const t = cellCenterPx(ev.target_position.x, ev.target_position.y);
      circles.push({ key: `impact-${ev.turn}-${ev.actor_id}`, cx: t.cx, cy: t.cy, type: "attack" });
    }
    if (ev.type === "RESULT" && ev.markers?.includes("DOWN") && ev.target_position) {
      const t = cellCenterPx(ev.target_position.x, ev.target_position.y);
      circles.push({ key: `impact-${ev.turn}-kill`, cx: t.cx, cy: t.cy, type: "kill" });
    }
  }
  return circles;
});

const deathCrosses = computed(() => {
  const frame = props.frame;
  if (!frame) return [];
  const crosses: Array<{ key: string; x1: number; y1: number; x2: number; y2: number }> = [];
  for (const ev of frame.events_structured) {
    if (ev.type === "RESULT" && ev.markers?.includes("DOWN") && ev.target_position) {
      const t = cellCenterPx(ev.target_position.x, ev.target_position.y);
      const s = 12;
      crosses.push({ key: `death-${ev.turn}`, x1: t.cx - s, y1: t.cy - s, x2: t.cx + s, y2: t.cy + s });
    }
  }
  return crosses;
});

function cellAria(cell: { x: number; y: number; fogDark?: boolean; unit?: unknown; terrainType: string }): string {
  if (cell.fogDark) return `位置 ${cell.x},${cell.y} 未探索`;
  const terrain = terrainLabel(cell.terrainType);
  if (cell.unit && typeof cell.unit === "object" && "agent_id" in (cell.unit as object)) {
    const u = cell.unit as { agent_id: string; team: string; role: string };
    return `${u.agent_id} ${u.team === "red" ? "红方" : "蓝方"} ${u.role} 位于 ${terrain}`;
  }
  return `格子 ${cell.x},${cell.y} ${terrain}`;
}

function handleCellClick(cell: { x: number; y: number; fogDark?: boolean; unit?: Record<string, unknown> }) {
  if (cell.fogDark) return;
  if (cell.unit && typeof cell.unit === "object" && "agent_id" in cell.unit) {
    const agentId = String(cell.unit.agent_id);
    emit("focus-agent", agentId);
    showRange.value = true;
    rangeCells.value = computeReachableCells(agentId);
  } else {
    showRange.value = false;
    rangeCells.value = new Set();
  }
}

const terrainMMColors: Record<string, string> = {
  open: "#ede6d4", road: "#c8b898", forest: "#5d9a3e", urban: "#9a8470",
  water: "#3898c8", rough: "#c8a668", marsh: "#5a8a58", mountain: "#a08868",
};

function drawMinimap(frame: BattleFrame) {
  const canvas = minimapRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const cw = minimapW / frame.map.width;
  const ch = minimapH / frame.map.height;
  ctx.clearRect(0, 0, minimapW, minimapH);
  for (let y = 0; y < frame.map.height; y++) {
    for (let x = 0; x < frame.map.width; x++) {
      const tt = getTerrainType(x, y);
      ctx.fillStyle = terrainMMColors[tt] ?? "#ede6d4";
      ctx.fillRect(x * cw, y * ch, cw, ch);
    }
  }
  for (const u of frame.units) {
    if (!u.alive) continue;
    ctx.fillStyle = u.team === "red" ? "#ef4444" : "#3b82f6";
    ctx.beginPath();
    ctx.arc(u.pos.x * cw + cw / 2, u.pos.y * ch + ch / 2, 3, 0, Math.PI * 2);
    ctx.fill();
  }
}

function onMinimapClick(e: MouseEvent) {
  const el = minimapRef.value;
  if (!el || !props.frame) return;
  const rect = el.getBoundingClientRect();
  const px = (e.clientX - rect.left) / minimapW;
  const py = (e.clientY - rect.top) / minimapH;
  const wx = Math.round(px * props.frame.map.width);
  const wy = Math.round(py * props.frame.map.height);
  if (boardScrollRef.value) {
    const scrollToX = boardPad + wx * hexWidth + (wy % 2 ? hexWidth / 2 : 0) - boardScrollRef.value.clientWidth / 2;
    const scrollToY = boardPad + wy * rowStep - boardScrollRef.value.clientHeight / 2;
    boardScrollRef.value.scrollTo({ left: Math.max(0, scrollToX), top: Math.max(0, scrollToY), behavior: "smooth" });
  }
}

function showTooltip(cell: { x: number; y: number; fogDark?: boolean }): boolean {
  if (cell.fogDark) return false;
  return !!(
    hoveredPos.value &&
    hoveredPos.value.x === cell.x &&
    hoveredPos.value.y === cell.y &&
    props.frame?.map.terrain
  );
}
</script>
