<template>
  <section class="section-card stage-card" :class="`stage-density-${props.density}`" :style="stageStyle">
    <div class="battle-stage-head">
      <div class="battle-stage-titleblock">
        <div class="eyebrow stage-kicker">Main Theatre</div>
        <h2>战场实况</h2>
      </div>
      <div class="stage-head-actions">
        <div class="stage-view-switch" aria-label="战场视图模式">
          <button
            v-for="mode in viewModes"
            :key="mode.value"
            type="button"
            class="stage-view-chip"
            :class="{ active: props.density === mode.value }"
            @click="emit('update:density', mode.value)"
          >
            {{ mode.label }}
          </button>
        </div>
        <div class="stage-live-chip">{{ liveChip }}</div>
      </div>
    </div>

    <div v-if="frame" class="stage-control-track">
      <div class="stage-control-buttons">
        <button type="button" class="icon-control-btn" title="回到起点" :disabled="!battleStore.frames.length" @click="battleStore.seekToStart()">|‹</button>
        <button type="button" class="icon-control-btn" title="上一帧" :disabled="battleStore.currentTurn <= 0" @click="battleStore.stepBackward()">‹</button>
        <button type="button" class="play-control-btn" :disabled="battleStore.frames.length < 2" @click="battleStore.togglePlayback()">
          {{ battleStore.isPlaying ? "暂停" : "播放" }}
        </button>
        <button type="button" class="icon-control-btn" title="下一帧" :disabled="battleStore.currentTurn >= maxFrameIndex" @click="battleStore.stepForward()">›</button>
        <button type="button" class="icon-control-btn" title="跳到最新" :disabled="!battleStore.frames.length" @click="battleStore.seekToLatest()">›|</button>
      </div>

      <input
        v-model.number="battleStore.currentTurn"
        class="stage-timeline-slider"
        :max="maxFrameIndex"
        min="0"
        type="range"
        @input="battleStore.pause()"
      />

      <div class="stage-speed-row">
        <button
          v-for="speed in speedOptions"
          :key="speed"
          type="button"
          class="speed-chip"
          :class="{ active: battleStore.playbackSpeed === speed }"
          @click="battleStore.setPlaybackSpeed(speed)"
        >
          {{ speed }}x
        </button>
      </div>
    </div>

    <div v-if="frame" class="stage-marker-row">
      <button
        v-for="marker in recentMarkers"
        :key="marker.id"
        type="button"
        class="timeline-marker-pill compact"
        :class="marker.type.toLowerCase()"
        @click="seekToMarker(marker)"
      >
        {{ marker.label }} · T{{ marker.turn }}
      </button>
      <span v-if="!recentMarkers.length" class="stage-marker-empty">暂无关键标记</span>
    </div>

    <div v-if="frame" ref="mapStageRef" class="map-stage">
      <div class="map-board-shell battle-grid-panel">
        <div class="map-column-labels" :style="columnLabelStyle">
          <span v-for="column in displayColumns" :key="`col-${column}`">{{ columnLabel(column - 1) }}</span>
        </div>

        <div class="map-board-body">
          <div class="map-row-labels" :style="rowLabelStyle">
            <span v-for="row in displayRows" :key="`row-${row}`">{{ rowLabel(row - 1) }}</span>
          </div>

          <div ref="mapCanvasRef" class="map-board-canvas">
            <svg class="map-overlay" :width="boardPixelWidth" :height="boardPixelHeight" :viewBox="`0 0 ${boardPixelWidth} ${boardPixelHeight}`">
              <line
                v-for="(line, index) in relationLines"
                :key="`line-${index}`"
                :x1="line.x1"
                :y1="line.y1"
                :x2="line.x2"
                :y2="line.y2"
                class="relation-line"
              />
              <circle
                v-for="(circle, index) in lockedCircles"
                :key="`circle-${index}`"
                :cx="circle.cx"
                :cy="circle.cy"
                :r="circle.r"
                class="locked-ring"
              />
            </svg>

            <div
              class="map-grid"
              :style="gridStyle"
            >
              <template v-for="y in displayRows" :key="y - 1">
                <div
                  v-for="x in displayColumns"
                  :key="`${x - 1}-${y - 1}`"
                  class="map-cell"
                  :class="cellClass(cellAt(x - 1, y - 1), x - 1, y - 1)"
                  @mouseenter="cellAt(x - 1, y - 1) && battleStore.setHoveredAgent(cellAt(x - 1, y - 1)!.agent_id)"
                  @mouseleave="battleStore.setHoveredAgent('')"
                  @click="cellAt(x - 1, y - 1) && battleStore.setFocusedAgent(cellAt(x - 1, y - 1)!.agent_id)"
                >
                  <div v-if="isSpawnZone('red', x - 1, y - 1)" class="zone-tag red-spawn"></div>
                  <div v-if="isSpawnZone('blue', x - 1, y - 1)" class="zone-tag blue-spawn"></div>
                  <div v-if="isControlZone(x - 1, y - 1)" class="zone-tag control-zone"></div>
                  <div v-if="isPrimaryControlCell(x - 1, y - 1)" class="control-zone-label">CONTROL</div>
                  <div v-for="(effect, index) in cellEffects(x - 1, y - 1)" :key="`${x - 1}-${y - 1}-fx-${index}`" class="cell-effect" :class="effect"></div>

                  <template v-if="cellAt(x - 1, y - 1)">
                    <div class="cell-card-bar" :class="`team-${cellAt(x - 1, y - 1)!.team}`"></div>
                    <div v-if="lockedTargets.has(cellAt(x - 1, y - 1)!.agent_id)" class="cell-alert-dot"></div>
                    <div class="cell-status-row">
                      <span class="cell-state-chip" :class="unitStateTone(cellAt(x - 1, y - 1)!.agent_id)">{{ unitStateLabel(cellAt(x - 1, y - 1)!.agent_id) }}</span>
                    </div>
                    <div v-if="statusBadges(cellAt(x - 1, y - 1)!.agent_id).length" class="cell-badges">
                      <span v-for="badge in statusBadges(cellAt(x - 1, y - 1)!.agent_id).slice(0, 2)" :key="`${cellAt(x - 1, y - 1)!.agent_id}-${badge}`" class="cell-badge" :class="badge">
                        {{ badgeShortLabel(badge) }}
                      </span>
                    </div>
                    <div class="tactical-unit-core">
                      <span class="cell-role">{{ roleCode(cellAt(x - 1, y - 1)!.role) }}</span>
                      <span class="cell-id">{{ teamShort(cellAt(x - 1, y - 1)!.team) }}{{ cellIndex(cellAt(x - 1, y - 1)!.agent_id) }}</span>
                    </div>
                    <div class="tactical-attr-row">
                      <span>MP {{ unitMove(cellAt(x - 1, y - 1)!.agent_id) }}</span>
                      <span>RG {{ unitRange(cellAt(x - 1, y - 1)!.agent_id) }}</span>
                    </div>
                    <div class="tactical-resource-row">
                      <span>HP {{ unitHpPercent(cellAt(x - 1, y - 1)!.agent_id) }}%</span>
                      <span>AM {{ unitAmmo(cellAt(x - 1, y - 1)!.agent_id) }}</span>
                    </div>

                    <div v-if="battleStore.hoveredAgentId === cellAt(x - 1, y - 1)!.agent_id" class="cell-popover">
                      <strong>{{ cellAt(x - 1, y - 1)!.agent_id }}</strong>
                      <span>{{ unitMeta(cellAt(x - 1, y - 1)!.agent_id) }}</span>
                    </div>
                  </template>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="frame" class="stage-live-footer">
      <span>ROUND {{ frame.turn }}</span>
      <span>FRAME {{ currentFrameIndex }}/{{ frameCount }}</span>
      <span>ACTIVE {{ aliveUnits }}</span>
      <span>EFFECTS {{ frame.effect_details.length }}</span>
    </div>

    <div v-else class="empty-state">创建并启动一局演练后，这里会显示地图。</div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import type { BattleFrame } from "../types";
import { useBattleStore } from "../stores/battle";

type MapViewMode = "fit" | "compact" | "standard" | "expanded";

const props = withDefaults(defineProps<{ frame: BattleFrame | null; density?: MapViewMode }>(), {
  density: "fit",
});
const emit = defineEmits<{ "update:density": [value: MapViewMode] }>();
const battleStore = useBattleStore();
const mapCanvasRef = ref<HTMLElement | null>(null);
const mapStageRef = ref<HTMLElement | null>(null);
const stageSize = ref({ width: 0, height: 0 });
let resizeObserver: ResizeObserver | null = null;
const aliveUnits = computed(() => props.frame?.units.filter((unit) => unit.alive).length ?? 0);
const focusedSummary = computed(() => battleStore.focusedUnit);
const speedOptions = [0.5, 1, 2, 4];
const viewModes: Array<{ label: string; value: MapViewMode }> = [
  { label: "Fit", value: "fit" },
  { label: "60", value: "compact" },
  { label: "72", value: "standard" },
  { label: "84", value: "expanded" },
];
const cellSize = computed(() => {
  if (props.density === "fit") return 72;
  if (props.density === "compact") return 60;
  if (props.density === "expanded") return 84;
  return 72;
});
const gridGap = 6;
const gridPadding = 6;
const displayColumns = computed(() => {
  const frame = props.frame;
  if (!frame) return 0;
  if (props.density !== "fit") return frame.map.width;
  const available = Math.max(0, stageSize.value.width - 40);
  const columns = Math.floor((available - gridPadding * 2 + gridGap) / (cellSize.value + gridGap));
  return Math.max(frame.map.width, columns || frame.map.width);
});
const displayRows = computed(() => {
  const frame = props.frame;
  if (!frame) return 0;
  if (props.density !== "fit") return frame.map.height;
  const available = Math.max(0, stageSize.value.height - 34);
  const rows = Math.floor((available - gridPadding * 2 + gridGap) / (cellSize.value + gridGap));
  return Math.max(frame.map.height, rows || frame.map.height);
});
const boardOffsetX = computed(() => {
  const width = props.frame?.map.width ?? 0;
  return Math.max(0, Math.floor((displayColumns.value - width) / 2));
});
const boardOffsetY = computed(() => {
  const height = props.frame?.map.height ?? 0;
  return Math.max(0, Math.floor((displayRows.value - height) / 2));
});
const boardPixelWidth = computed(() => {
  if (!props.frame) return 0;
  return displayColumns.value * cellSize.value + Math.max(0, displayColumns.value - 1) * gridGap + gridPadding * 2;
});
const boardPixelHeight = computed(() => {
  if (!props.frame) return 0;
  return displayRows.value * cellSize.value + Math.max(0, displayRows.value - 1) * gridGap + gridPadding * 2;
});
const stageStyle = computed(() => ({
  "--battle-cell-size": `${cellSize.value}px`,
  "--battle-grid-gap": `${gridGap}px`,
  "--battle-grid-padding": `${gridPadding}px`,
}));
const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${displayColumns.value}, var(--battle-cell-size))`,
  gridTemplateRows: `repeat(${displayRows.value}, var(--battle-cell-size))`,
}));
const columnLabelStyle = computed(() => ({
  gridTemplateColumns: `repeat(${displayColumns.value}, var(--battle-cell-size))`,
  width: `${displayColumns.value ? displayColumns.value * cellSize.value + Math.max(0, displayColumns.value - 1) * gridGap : 0}px`,
}));
const rowLabelStyle = computed(() => ({
  gridTemplateRows: `repeat(${displayRows.value}, var(--battle-cell-size))`,
  height: `${displayRows.value ? displayRows.value * cellSize.value + Math.max(0, displayRows.value - 1) * gridGap : 0}px`,
}));
const maxFrameIndex = computed(() => Math.max(0, battleStore.frames.length - 1));
const currentFrameIndex = computed(() => battleStore.frames.length ? battleStore.currentTurn + 1 : 0);
const frameCount = computed(() => Math.max(1, battleStore.frames.length));
const recentMarkers = computed(() => battleStore.timelineMarkers.slice(-8).reverse());
const liveChip = computed(() => {
  if (!props.frame) return "LIVE / IDLE";
  return `LIVE / ROUND ${props.frame.turn}`;
});
const activeAgentId = computed(() => {
  const latest = props.frame?.events?.[props.frame.events.length - 1] ?? "";
  const match = latest.match(/(red|blue)_[a-z_]+_\d+/);
  return match?.[0] ?? "";
});
const lockedTargets = computed(() => {
  if (!props.frame) return new Set<string>();
  return new Set(
    [props.frame.memory.red.summary?.primary_threat, props.frame.memory.blue.summary?.primary_threat]
      .filter((value): value is string => Boolean(value)),
  );
});
const lockedUnits = computed(() => {
  if (!props.frame) return [];
  return props.frame.units.filter((unit) => lockedTargets.value.has(unit.agent_id));
});
const relationLines = computed(() => {
  if (!focusedSummary.value || !lockedUnits.value.length || !props.frame) return [];
  return lockedUnits.value
    .filter((unit) => unit.agent_id !== focusedSummary.value?.agent_id)
    .map((unit) => ({
      x1: cellCenterX(focusedSummary.value!.pos.x),
      y1: cellCenterY(focusedSummary.value!.pos.y),
      x2: cellCenterX(unit.pos.x),
      y2: cellCenterY(unit.pos.y),
    }));
});
const lockedCircles = computed(() => {
  if (!props.frame) return [];
  return lockedUnits.value.map((unit) => ({
    cx: cellCenterX(unit.pos.x),
    cy: cellCenterY(unit.pos.y),
    r: Math.max(16, cellSize.value * 0.32),
  }));
});

watch(
  () => [battleStore.focusedAgentId, battleStore.currentTurn, props.density],
  () => {
    nextTick(() => scrollFocusedIntoView());
  },
);

onMounted(() => {
  resizeObserver = new ResizeObserver(([entry]) => {
    if (!entry) return;
    stageSize.value = {
      width: entry.contentRect.width,
      height: entry.contentRect.height,
    };
  });
  if (mapStageRef.value) {
    resizeObserver.observe(mapStageRef.value);
  }
});

onUnmounted(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
});

watch(mapStageRef, (element, previous) => {
  if (!resizeObserver) return;
  if (previous) resizeObserver.unobserve(previous);
  if (element) resizeObserver.observe(element);
});
function cellClass(cell: BattleFrame["map"]["cells"][number][number], x: number, y: number) {
  if (!isConfiguredCell(x, y)) return "inactive";
  if (!cell) return "empty";
  return {
    [`team-${cell.team}`]: true,
    focused: battleStore.focusedAgentId === cell.agent_id,
    hovered: battleStore.hoveredAgentId === cell.agent_id,
    active: activeAgentId.value === cell.agent_id,
    locked: lockedTargets.value.has(cell.agent_id),
    exposed: unitState(cell.agent_id)?.exposed_turns_remaining,
    jammed: unitState(cell.agent_id)?.jammed_turns_remaining,
    guarded: unitState(cell.agent_id)?.status_flags.includes("guarded"),
    supported: unitState(cell.agent_id)?.status_flags.includes("supported"),
    blocked: unitState(cell.agent_id)?.status_flags.includes("blocked"),
    contested: isControlZone(x, y),
  };
}

function cellAt(x: number, y: number) {
  const world = toWorldCell(x, y);
  if (!isConfiguredCell(x, y)) return null;
  return props.frame?.map.cells[world.y]?.[world.x] ?? null;
}

function isConfiguredCell(x: number, y: number) {
  const frame = props.frame;
  if (!frame) return false;
  const world = toWorldCell(x, y);
  return world.x >= 0 && world.y >= 0 && world.x < frame.map.width && world.y < frame.map.height;
}

function unitMeta(agentId: string) {
  const unit = props.frame?.units.find((item) => item.agent_id === agentId);
  if (!unit) return "暂无数据";
  const flags = unit.status_flags?.length ? ` · 状态 ${unit.status_flags.join("/")}` : "";
  const mp = unit.movement_points || unit.move_speed;
  return `${unit.role_label} · HP ${unit.hp}/${unit.max_hp} · 资源 ${unit.ammo}/${unit.max_ammo} · MP ${mp} · 射程 ${unitRange(agentId)} · 技能 ${unit.skill_name}${flags}`;
}

function toWorldCell(x: number, y: number) {
  return {
    x: x - boardOffsetX.value,
    y: y - boardOffsetY.value,
  };
}

function cellCenterX(index: number) {
  return gridPadding + (index + boardOffsetX.value) * (cellSize.value + gridGap) + cellSize.value / 2;
}

function cellCenterY(index: number) {
  return gridPadding + (index + boardOffsetY.value) * (cellSize.value + gridGap) + cellSize.value / 2;
}

function rowLabel(index: number) {
  const worldY = index - boardOffsetY.value;
  if (!props.frame || worldY < 0 || worldY >= props.frame.map.height) return "";
  return String.fromCharCode(65 + worldY);
}

function columnLabel(index: number) {
  const worldX = index - boardOffsetX.value;
  if (!props.frame || worldX < 0 || worldX >= props.frame.map.width) return "";
  return String(worldX + 1);
}

function unitState(agentId: string) {
  return props.frame?.units.find((unit) => unit.agent_id === agentId) ?? null;
}

function inZone(zone: BattleFrame["map"]["control_zones"][number], x: number, y: number) {
  const world = toWorldCell(x, y);
  return world.x >= zone.x && world.x < zone.x + zone.width && world.y >= zone.y && world.y < zone.y + zone.height;
}

function isControlZone(x: number, y: number) {
  return props.frame?.map.control_zones.some((zone) => inZone(zone, x, y)) ?? false;
}

function isPrimaryControlCell(x: number, y: number) {
  const zone = props.frame?.map.control_zones[0];
  if (!zone) return false;
  const world = toWorldCell(x, y);
  return world.x === zone.x && world.y === zone.y;
}

function isSpawnZone(team: "red" | "blue", x: number, y: number) {
  const zones = team === "red" ? props.frame?.map.red_spawn_zones : props.frame?.map.blue_spawn_zones;
  return zones?.some((zone) => inZone(zone, x, y)) ?? false;
}

function cellEffects(x: number, y: number) {
  const effects = props.frame?.map.effects ?? [];
  const world = toWorldCell(x, y);
  return effects
    .filter((effect) => {
      const center = effect.center as { x: number; y: number } | undefined;
      const radius = Number(effect.radius ?? 0);
      if (!center) return false;
      return Math.abs(center.x - world.x) + Math.abs(center.y - world.y) <= radius;
    })
    .map((effect) => String(effect.type ?? "effect"));
}

function statusBadges(agentId: string) {
  return unitState(agentId)?.status_flags ?? [];
}

function badgeShortLabel(flag: string) {
  const labels: Record<string, string> = {
    exposed: "揭示",
    jammed: "干扰",
    guarded: "护卫",
    supported: "支援",
    locked: "锁定",
    blocked: "封锁",
    engaging: "接敌",
  };
  return labels[flag] ?? flag.slice(0, 2);
}

function roleCode(role: string) {
  const labels: Record<string, string> = {
    coordinator: "CO",
    scout: "SC",
    attacker: "AT",
    defender: "DF",
    support: "SP",
    jammer: "JM",
    controller: "CT",
    assaulter: "AS",
  };
  return labels[role] ?? role.slice(0, 2).toUpperCase();
}

function teamShort(team: "red" | "blue") {
  return team === "red" ? "RED" : "BLUE";
}

function cellIndex(agentId: string) {
  const match = agentId.match(/_(\d+)$/);
  return match?.[1] ?? "1";
}

function unitMove(agentId: string) {
  const unit = unitState(agentId);
  return unit?.movement_points ?? unit?.move_speed ?? "-";
}

function unitRange(agentId: string) {
  const unit = unitState(agentId);
  if (!unit) return "-";
  const roleRanges: Record<string, number> = {
    coordinator: 1,
    scout: 1,
    attacker: 2,
    defender: 1,
    support: 1,
    jammer: 1,
    controller: 1,
    assaulter: 1,
  };
  return roleRanges[unit.role] ?? 1;
}

function unitHpPercent(agentId: string) {
  const unit = unitState(agentId);
  if (!unit || !unit.max_hp) return "-";
  return Math.max(0, Math.round((unit.hp / unit.max_hp) * 100));
}

function unitAmmo(agentId: string) {
  const unit = unitState(agentId);
  if (!unit) return "-";
  return `${unit.ammo}/${unit.max_ammo}`;
}

function unitStateLabel(agentId: string) {
  const unit = unitState(agentId);
  if (!unit) return "待命";
  if (activeAgentId.value === agentId) return "行动中";
  if (!unit.alive || unit.hp <= 0) return "失效";
  if (unit.status_flags.includes("jammed")) return "受扰";
  if (unit.status_flags.includes("blocked")) return "受阻";
  if (unit.hp <= Math.ceil(unit.max_hp * 0.45)) return "受损";
  if (unit.status_flags.includes("guarded")) return "护卫";
  return "待命";
}

function unitStateTone(agentId: string) {
  const unit = unitState(agentId);
  if (!unit) return "idle";
  if (activeAgentId.value === agentId) return "active";
  if (unit.status_flags.includes("jammed")) return "jammed";
  if (unit.hp <= Math.ceil(unit.max_hp * 0.45)) return "damaged";
  if (unit.status_flags.includes("blocked")) return "blocked";
  return "idle";
}

function seekToMarker(marker: { turn: number; actor_id?: string | null; target_id?: string | null }) {
  battleStore.pause();
  battleStore.currentTurn = Math.min(marker.turn, Math.max(0, battleStore.frames.length - 1));
  if (marker.actor_id) {
    battleStore.setFocusedAgent(marker.actor_id);
  } else if (marker.target_id) {
    battleStore.setFocusedAgent(marker.target_id);
  }
}

function scrollFocusedIntoView() {
  const focused = focusedSummary.value;
  const canvas = mapCanvasRef.value;
  if (!focused || !canvas) return;
  const targetLeft = gridPadding + (focused.pos.x + boardOffsetX.value) * (cellSize.value + gridGap);
  const targetTop = gridPadding + (focused.pos.y + boardOffsetY.value) * (cellSize.value + gridGap);
  const targetCenterX = targetLeft + cellSize.value / 2;
  const targetCenterY = targetTop + cellSize.value / 2;
  canvas.scrollTo({
    left: Math.max(0, targetCenterX - canvas.clientWidth / 2),
    top: Math.max(0, targetCenterY - canvas.clientHeight / 2),
    behavior: "smooth",
  });
}
</script>
