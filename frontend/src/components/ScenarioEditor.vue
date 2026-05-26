<template>
  <section v-if="deploymentStore.scenarioConfig" class="section-card scenario-editor-card">
    <div class="section-head">
      <div>
        <div class="eyebrow">Scenario Sandbox</div>
        <h2>场景沙盘</h2>
      </div>
      <div class="scenario-legend">
        <span class="legend-pill red">红方出生区</span>
        <span class="legend-pill blue">蓝方出生区</span>
        <span class="legend-pill control">控制区</span>
      </div>
    </div>

    <div class="scenario-editor-layout">
      <div class="scenario-workbench">
        <div class="scenario-size-row">
          <label>
            宽度
            <input :value="scenario.width" type="number" min="6" max="24" @input="updateScenarioSize('width', $event)" />
          </label>
          <label>
            高度
            <input :value="scenario.height" type="number" min="6" max="24" @input="updateScenarioSize('height', $event)" />
          </label>
        </div>

        <div
          ref="boardRef"
          class="scenario-board"
          :style="boardStyle"
          @mousedown.self="clearSelection"
        >
          <button
            v-for="zone in allZones"
            :key="zone.key"
            type="button"
            class="scenario-zone"
            :class="[zone.team, { selected: isSelected(zone.team, zone.index) }]"
            :style="zoneStyle(zone.zone)"
            @mousedown.stop="startMove(zone.team, zone.index, $event)"
          >
            <span class="scenario-zone-label">{{ zoneLabel(zone.team, zone.index) }}</span>
            <span
              v-for="handle in handles"
              :key="handle"
              class="zone-handle"
              :class="handle"
              @mousedown.stop="startResize(zone.team, zone.index, handle, $event)"
            />
          </button>
        </div>

        <div class="scenario-selection-pills">
          <button
            v-for="zone in allZones"
            :key="`${zone.key}-pill`"
            type="button"
            class="selection-pill"
            :class="[zone.team, { active: isSelected(zone.team, zone.index) }]"
            @click="deploymentStore.selectZone(zone.team, zone.index)"
          >
            {{ zoneLabel(zone.team, zone.index) }}
          </button>
        </div>
      </div>

      <aside class="scenario-sidepanel">
        <div class="scenario-sidecard">
          <div class="eyebrow">Selected Zone</div>
          <template v-if="selectedZone">
            <h3>{{ zoneLabel(selectedZone.team, selectedZone.index) }}</h3>
            <div class="selected-zone-grid">
              <label v-for="field in zoneFields" :key="field">
                {{ fieldLabel(field) }}
                <input
                  :value="selectedZone.zone[field]"
                  type="number"
                  min="0"
                  @input="updateZoneField(field, $event)"
                />
              </label>
            </div>
            <p class="panel-copy subtle">主交互以拖拽和缩放为主，这里用于精确微调坐标与尺寸。</p>
          </template>
          <div v-else class="empty-state compact">请选择一个区域开始编辑。</div>
        </div>

        <div class="scenario-sidecard">
          <div class="eyebrow">Zone Summary</div>
          <div class="zone-summary-list">
            <div class="zone-summary-row">
              <span>红方出生区</span>
              <strong>{{ summaryText("red") }}</strong>
            </div>
            <div class="zone-summary-row">
              <span>蓝方出生区</span>
              <strong>{{ summaryText("blue") }}</strong>
            </div>
            <div class="zone-summary-row">
              <span>控制区</span>
              <strong>{{ summaryText("control") }}</strong>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { useDeploymentStore } from "../stores/deployment";
import type { RectZone, SelectedZoneRef, TeamKey } from "../types";

type Handle = "n" | "e" | "s" | "w" | "nw" | "ne" | "sw" | "se";

const deploymentStore = useDeploymentStore();
const boardRef = ref<HTMLElement | null>(null);
const zoneFields = ["x", "y", "width", "height"] as const;
const handles: Handle[] = ["n", "e", "s", "w", "nw", "ne", "sw", "se"];

const scenario = computed(() => deploymentStore.scenarioConfig!);
const selectedZone = computed(() => {
  const selected = deploymentStore.selectedZone;
  if (!selected || !deploymentStore.scenarioConfig) return null;
  const zone = zoneFromRef(selected);
  return zone ? { ...selected, zone } : null;
});

const allZones = computed(() => [
  ...scenario.value.red_spawn_zones.map((zone, index) => ({ key: `red-${index}`, team: "red" as const, index, zone })),
  ...scenario.value.blue_spawn_zones.map((zone, index) => ({ key: `blue-${index}`, team: "blue" as const, index, zone })),
  ...scenario.value.control_zones.map((zone, index) => ({ key: `control-${index}`, team: "control" as const, index, zone })),
]);

const boardStyle = computed(() => ({
  "--cols": String(scenario.value.width),
  "--rows": String(scenario.value.height),
} as Record<string, string>));

let activeCleanup: (() => void) | null = null;

function percent(value: number, total: number) {
  return `${(value / total) * 100}%`;
}

function zoneStyle(zone: RectZone) {
  return {
    left: percent(zone.x, scenario.value.width),
    top: percent(zone.y, scenario.value.height),
    width: percent(zone.width, scenario.value.width),
    height: percent(zone.height, scenario.value.height),
  };
}

function zoneFromRef(selected: SelectedZoneRef) {
  const currentScenario = deploymentStore.scenarioConfig;
  if (!currentScenario) return null;
  return (
    selected.team === "red"
      ? currentScenario.red_spawn_zones[selected.index]
      : selected.team === "blue"
        ? currentScenario.blue_spawn_zones[selected.index]
        : currentScenario.control_zones[selected.index]
  ) ?? null;
}

function summaryText(team: TeamKey | "control") {
  const zones = team === "red"
    ? scenario.value.red_spawn_zones
    : team === "blue"
      ? scenario.value.blue_spawn_zones
      : scenario.value.control_zones;
  return zones.map((zone) => `${zone.width}x${zone.height}@${zone.x},${zone.y}`).join(" / ");
}

function fieldLabel(field: typeof zoneFields[number]) {
  return {
    x: "X",
    y: "Y",
    width: "宽",
    height: "高",
  }[field];
}

function zoneLabel(team: TeamKey | "control", index: number) {
  const prefix = team === "red" ? "RED" : team === "blue" ? "BLUE" : "CTRL";
  return `${prefix} ${index + 1}`;
}

function isSelected(team: TeamKey | "control", index: number) {
  return deploymentStore.selectedZone?.team === team && deploymentStore.selectedZone?.index === index;
}

function clearSelection() {
  deploymentStore.ensureSelectedZone();
}

function updateScenarioSize(field: "width" | "height", event: Event) {
  const value = Number((event.target as HTMLInputElement).value);
  const width = field === "width" ? value : scenario.value.width;
  const height = field === "height" ? value : scenario.value.height;
  deploymentStore.setScenarioSize(width, height);
}

function updateZoneField(field: typeof zoneFields[number], event: Event) {
  if (!selectedZone.value) return;
  deploymentStore.updateZone(selectedZone.value.team, selectedZone.value.index, field, Number((event.target as HTMLInputElement).value));
}

function startMove(team: TeamKey | "control", index: number, event: MouseEvent) {
  startInteraction(team, index, "move", event);
}

function startResize(team: TeamKey | "control", index: number, handle: Handle, event: MouseEvent) {
  startInteraction(team, index, handle, event);
}

function startInteraction(team: TeamKey | "control", index: number, mode: Handle | "move", event: MouseEvent) {
  const board = boardRef.value;
  const zone = zoneFromRef({ team, index });
  if (!board || !zone) return;
  deploymentStore.selectZone(team, index);
  const startZone = { ...zone };
  const rect = board.getBoundingClientRect();
  const cellWidth = rect.width / scenario.value.width;
  const cellHeight = rect.height / scenario.value.height;
  const startX = event.clientX;
  const startY = event.clientY;

  const onMove = (moveEvent: MouseEvent) => {
    const deltaX = Math.round((moveEvent.clientX - startX) / cellWidth);
    const deltaY = Math.round((moveEvent.clientY - startY) / cellHeight);
    if (mode === "move") {
      deploymentStore.moveZone(team, index, startZone.x + deltaX, startZone.y + deltaY);
      return;
    }
    const next = { ...startZone };
    if (mode.includes("e")) next.width = startZone.width + deltaX;
    if (mode.includes("s")) next.height = startZone.height + deltaY;
    if (mode.includes("w")) {
      next.x = startZone.x + deltaX;
      next.width = startZone.width - deltaX;
    }
    if (mode.includes("n")) {
      next.y = startZone.y + deltaY;
      next.height = startZone.height - deltaY;
    }
    deploymentStore.replaceZone(team, index, next);
  };

  const onUp = () => {
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
    activeCleanup = null;
  };

  activeCleanup?.();
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);
  activeCleanup = () => {
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
  };
}

onBeforeUnmount(() => {
  activeCleanup?.();
});
</script>
