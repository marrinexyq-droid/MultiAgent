<template>
  <main class="page battle-page" :class="`${battleViewMode}-mode`">
    <section class="battle-statusbar section-card theatre-hud">
      <div class="battle-status-meta battle-status-overview">
        <div class="eyebrow">Theatre Command</div>
        <strong>{{ battleStore.battleId || "pending" }} · Round {{ roundProgress }}</strong>
        <div class="battle-status-inline battle-status-summary">
          <span>{{ statusLabel }}</span>
          <span class="hud-team red">RED {{ redAliveUnits }}</span>
          <span class="hud-team blue">BLUE {{ blueAliveUnits }}</span>
          <span>Events {{ keyEventCount }}</span>
          <span>Effects {{ activeEffects }}</span>
        </div>
      </div>
      <div class="battle-status-actions">
        <button
          class="ghost-btn compact-btn"
          :class="{ active: battleViewMode === 'theatre' }"
          @click="battleViewMode = 'theatre'"
        >
          全屏战场
        </button>
        <button
          class="ghost-btn compact-btn analysis-toggle"
          :class="{ active: battleViewMode === 'analysis' }"
          @click="battleViewMode = 'analysis'"
        >
          三栏分析
        </button>
        <RouterLink class="ghost-btn compact-btn" to="/deployment">返回部署</RouterLink>
        <button
          class="primary-btn compact-btn"
          :disabled="realtimeActionDisabled"
          :title="realtimeActionHint"
          @click="handleRealtimeAction"
        >
          {{ realtimeActionLabel }}
        </button>
        <RouterLink v-if="battleStore.battleId && battleStore.status !== 'done'" class="ghost-btn compact-btn" :to="`/review/${battleStore.battleId}`">查看结算</RouterLink>
      </div>
    </section>

    <section v-if="battleViewMode === 'analysis'" class="battle-grid-layout">
      <EventFeed :frame="battleStore.currentFrame" @open-archive="showAllEvents = true" />

      <section v-if="isHexFrame" class="battle-center-stage solo-stage battle-hex-stage analysis-hex-stage">
        <HexBattleMap
          :frame="battleStore.currentFrame"
          :focused-agent-id="battleStore.focusedAgentId"
          selected-team="all"
          :previous-frame="previousFrame"
          :show-diffs="showHexDiffs"
          :show-influence="showHexInfluence"
          :focused-unit-info="focusedUnitInfo"
          :timeline-markers="timelineBarData"
          @focus-agent="handleHexFocus"
          @jump="seekToMarker"
        />
        <BattleReplayControls
          :current-turn="battleStore.currentTurn"
          :frames-length="battleStore.frames.length"
          :is-playing="battleStore.isPlaying"
          :max-frame-index="maxFrameIndex"
          :playback-speed="battleStore.playbackSpeed"
          @start="battleStore.seekToStart()"
          @backward="battleStore.stepBackward()"
          @toggle-play="battleStore.togglePlayback()"
          @forward="battleStore.stepForward()"
          @latest="battleStore.seekToLatest()"
          @seek="seekReplayFrame"
          @speed="battleStore.setPlaybackSpeed"
        />
      </section>
      <section v-else class="battle-center-stage solo-stage">
        <BattleMap v-model:density="theatreDensity" :frame="battleStore.currentFrame" />
      </section>

      <aside class="battle-side-rail right-rail">
        <InfoColumn :frame="battleStore.currentFrame" />
      </aside>
    </section>

    <section v-else class="battle-theatre-layout">
      <section v-if="isHexFrame" class="battle-theatre-stage battle-hex-stage">
        <HexBattleMap
          :frame="battleStore.currentFrame"
          :focused-agent-id="battleStore.focusedAgentId"
          selected-team="all"
          :previous-frame="previousFrame"
          :show-diffs="showHexDiffs"
          :show-influence="showHexInfluence"
          :focused-unit-info="focusedUnitInfo"
          :timeline-markers="timelineBarData"
          @focus-agent="handleHexFocus"
          @jump="seekToMarker"
        />
        <BattleReplayControls
          :current-turn="battleStore.currentTurn"
          :frames-length="battleStore.frames.length"
          :is-playing="battleStore.isPlaying"
          :max-frame-index="maxFrameIndex"
          :playback-speed="battleStore.playbackSpeed"
          @start="battleStore.seekToStart()"
          @backward="battleStore.stepBackward()"
          @toggle-play="battleStore.togglePlayback()"
          @forward="battleStore.stepForward()"
          @latest="battleStore.seekToLatest()"
          @seek="seekReplayFrame"
          @speed="battleStore.setPlaybackSpeed"
        />
      </section>
      <section v-else class="battle-theatre-stage">
        <BattleMap v-model:density="theatreDensity" :frame="battleStore.currentFrame" />
      </section>

      <div class="theatre-event-ticker" :class="latestEventClass" @click="eventDrawerOpen = true">
        <span>{{ latestEventLabel }}</span>
        <strong>{{ latestEventText }}</strong>
      </div>

      <div class="theatre-floating-actions left">
        <button type="button" class="theatre-fab" @click="eventDrawerOpen = true">事件流</button>
      </div>

      <div class="theatre-floating-actions right">
        <button v-if="isHexFrame" type="button" class="theatre-fab" :class="{ active: showHexInfluence }" @click="showHexInfluence = !showHexInfluence">影响圈</button>
        <button v-if="isHexFrame" type="button" class="theatre-fab" :class="{ active: showHexDiffs }" @click="showHexDiffs = !showHexDiffs">帧差</button>
        <button type="button" class="theatre-fab" @click="openDecisionPanel('focus')">焦点</button>
        <button type="button" class="theatre-fab" @click="openDecisionPanel('intel')">情报</button>
      </div>

      <aside class="theatre-drawer event-drawer" :class="{ open: eventDrawerOpen }">
        <EventFeed :frame="battleStore.currentFrame" @open-archive="showAllEvents = true" />
      </aside>

      <aside class="theatre-drawer decision-drawer" :class="{ open: decisionDrawerOpen }">
        <div class="theatre-drawer-head">
          <div>
            <div class="eyebrow">Decision Drawer</div>
            <strong>{{ drawerTitle }}</strong>
          </div>
          <button type="button" class="ghost-btn compact-btn" @click="decisionDrawerOpen = false">关闭</button>
        </div>
        <InfoColumn :frame="battleStore.currentFrame" />
      </aside>

      <button
        v-if="eventDrawerOpen || decisionDrawerOpen"
        type="button"
        class="theatre-scrim"
        aria-label="关闭浮层"
        @click="closeDrawers"
      ></button>
    </section>

    <BattleOverlayPanel :open="showAllEvents" eyebrow="Event Archive" title="完整事件轨道" @close="showAllEvents = false">
      <div v-if="battleStore.timelineMarkers.length" class="overlay-block">
        <div class="marker-stack-title">关键标记</div>
        <div class="timeline-marker-row in-panel">
          <button
            v-for="marker in battleStore.timelineMarkers.slice().reverse()"
            :key="`overlay-${marker.id}`"
            type="button"
            class="timeline-marker-pill"
            :class="marker.type.toLowerCase()"
            @click="seekToMarker(marker); showAllEvents = false"
          >
            {{ marker.label }} · T{{ marker.turn }}
          </button>
        </div>
      </div>
      <div v-if="battleStore.currentFrame?.events?.length" class="list-stack">
        <div
          v-for="(event, index) in recentStructuredEvents"
          :key="`overlay-event-${event.turn}-${index}-${event.type}`"
          class="stack-card event-card clickable"
          @click="focusFromStructuredEvent(event); showAllEvents = false"
        >
          <div class="event-meta">
            <span>T{{ event.turn }}</span>
            <span :class="['event-type', event.type.toLowerCase()]">{{ event.type }}</span>
          </div>
          <p>{{ event.summary }}</p>
        </div>
      </div>
      <div v-else class="empty-state">暂无事件</div>
    </BattleOverlayPanel>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { useRouter } from "vue-router";
import BattleOverlayPanel from "../components/BattleOverlayPanel.vue";
import BattleMap from "../components/BattleMap.vue";
import BattleReplayControls from "../components/BattleReplayControls.vue";
import EventFeed from "../components/EventFeed.vue";
import HexBattleMap from "../components/HexBattleMap.vue";
import InfoColumn from "../components/InfoColumn.vue";
import { useBattleStore } from "../stores/battle";

const props = defineProps<{ id: string }>();
const battleStore = useBattleStore();
const router = useRouter();
const statusLabel = computed(() => {
  const map: Record<string, string> = {
    idle: "待命",
    created: "已创建",
    running: "推演中",
    paused: "已暂停",
    done: "已完成",
    error: "异常",
  };
  return map[battleStore.status] ?? battleStore.status;
});
const currentTurnDisplay = computed(() => battleStore.currentFrame?.turn ?? battleStore.currentTurn ?? 0);
const maxTurnsDisplay = computed(() => {
  const summary = battleStore.summary as { max_turns?: number } | null;
  return Math.max(summary?.max_turns ?? 0, battleStore.frames.length - 1, currentTurnDisplay.value, 1);
});
const roundProgress = computed(() => `${currentTurnDisplay.value}/${maxTurnsDisplay.value}`);
const recentStructuredEvents = computed(() => (battleStore.currentFrame?.events_structured ?? []).slice(-12).reverse());
const activeEffects = computed(() => battleStore.currentFrame?.effect_details?.length ?? 0);
const redAliveUnits = computed(() => battleStore.currentFrame?.units.filter((unit) => unit.team === "red" && unit.alive).length ?? 0);
const blueAliveUnits = computed(() => battleStore.currentFrame?.units.filter((unit) => unit.team === "blue" && unit.alive).length ?? 0);
const keyEventTypes = new Set(["RESULT", "DOWN", "ATTACK", "SPOT", "JAM", "BLOCK"]);
const keyEventCount = computed(() => (battleStore.currentFrame?.events_structured ?? []).filter((event) => keyEventTypes.has(event.type.toUpperCase())).length);
const showAllEvents = ref(false);
const eventDrawerOpen = ref(false);
const decisionDrawerOpen = ref(false);
const battleViewMode = ref<"theatre" | "analysis">("theatre");
const selectedPanel = ref<"focus" | "intel" | "effects" | "advice">("focus");
const theatreDensity = ref<"fit" | "compact" | "standard" | "expanded">("fit");
const showHexDiffs = ref(false);
const showHexInfluence = ref(false);
let replayTimer: ReturnType<typeof setTimeout> | null = null;
const maxFrameIndex = computed(() => Math.max(0, battleStore.frames.length - 1));
const isHexFrame = computed(() => battleStore.currentFrame?.map.grid_type === "hex");
const previousFrame = computed(() => battleStore.currentTurn > 0 ? battleStore.frames[battleStore.currentTurn - 1] ?? null : null);
const focusedUnitInfo = computed(() => {
  const unit = battleStore.focusedUnit;
  if (!unit) return null;
  return {
    vision: unit.vision_range,
    attack: unit.attack_range,
    pos: unit.pos,
  };
});
const timelineBarData = computed(() => {
  const maxTurn = Math.max(1, battleStore.frames.length - 1);
  return battleStore.timelineMarkers.map((marker) => ({
    ...marker,
    pct: (marker.turn / maxTurn) * 100,
  }));
});
const realtimeActionLabel = computed(() => {
  if (battleStore.status === "running") return "暂停推演";
  if (battleStore.status === "paused") return "继续推演";
  if (battleStore.status === "done") return "查看结算";
  if (battleStore.status === "error") return "重新连接推演";
  return "开始实时推演";
});
const realtimeActionDisabled = computed(() => !battleStore.battleId || battleStore.liveControlLoading);
const realtimeActionHint = computed(() => {
  if (battleStore.status === "running") return "暂停后后端会停止推进新回合，当前画面保持在最新帧。";
  if (battleStore.status === "paused") return "继续后端实时推演。";
  if (battleStore.status === "done") return "跳转结算查看完整复盘。";
  return "开始实时推演";
});
const latestEventText = computed(() => {
  const event = battleStore.currentFrame?.events_structured?.at(-1);
  if (event) return event.summary;
  return "等待战术事件写入";
});
const latestEventType = computed(() => battleStore.currentFrame?.events_structured?.at(-1)?.type.toUpperCase() ?? "IDLE");
const latestEventLabel = computed(() => {
  const labels: Record<string, string> = {
    RESULT: "RESULT",
    DOWN: "DOWN",
    ATTACK: "ATTACK",
    SPOT: "SPOT",
    JAM: "JAM",
    BLOCK: "BLOCK",
    IDLE: "EVENT",
  };
  return labels[latestEventType.value] ?? latestEventType.value;
});
const latestEventClass = computed(() => `event-${latestEventType.value.toLowerCase()}`);
const drawerTitle = computed(() => {
  const titles = {
    focus: "焦点单位",
    intel: "情报态势",
    effects: "技能影响",
    advice: "系统建议",
  };
  return titles[selectedPanel.value];
});

onMounted(() => {
  if (!battleStore.battleId) {
    battleStore.battleId = props.id;
  }
  if ((battleStore.status === "idle" || battleStore.status === "created") && battleStore.battleId) {
    startBattleNow();
  }
});

onUnmounted(() => {
  clearReplayTimer();
});

watch(
  [() => battleStore.isPlaying, () => battleStore.playbackSpeed, () => battleStore.currentTurn, () => battleStore.frames.length],
  () => {
    clearReplayTimer();
    if (!battleStore.isPlaying || battleStore.frames.length < 2) return;
    if (battleStore.currentTurn >= battleStore.frames.length - 1) {
      battleStore.pause();
      return;
    }
    replayTimer = setTimeout(() => {
      battleStore.currentTurn = Math.min(battleStore.currentTurn + 1, battleStore.frames.length - 1);
    }, Math.round(900 / battleStore.playbackSpeed));
  },
  { immediate: true },
);

watch(
  () => battleStore.focusedAgentId,
  (agentId) => {
    if (agentId && battleViewMode.value === "theatre") {
      openDecisionPanel("focus");
    }
  },
);

async function startBattleNow() {
  await battleStore.startRealtime();
}

async function handleRealtimeAction() {
  if (battleStore.status === "done" && battleStore.battleId) {
    await router.push(`/review/${battleStore.battleId}`);
    return;
  }
  if (battleStore.status === "running") {
    await battleStore.pauseRealtime();
    return;
  }
  if (battleStore.status === "paused") {
    await battleStore.resumeRealtime();
    return;
  }
  if (!realtimeActionDisabled.value) {
    await startBattleNow();
  }
}

function focusFromStructuredEvent(event: { actor_id?: string | null; target_id?: string | null; turn: number }) {
  battleStore.pause();
  battleStore.currentTurn = Math.min(event.turn, Math.max(0, battleStore.frames.length - 1));
  if (event.actor_id) {
    battleStore.setFocusedAgent(event.actor_id);
    return;
  }
  if (event.target_id) {
    battleStore.setFocusedAgent(event.target_id);
  }
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

function handleHexFocus(agentId: string) {
  battleStore.setFocusedAgent(agentId);
  if (battleViewMode.value === "theatre") {
    openDecisionPanel("focus");
  }
}

function seekReplayFrame(turn: number) {
  battleStore.currentTurn = turn;
  battleStore.pause();
}

function clearReplayTimer() {
  if (replayTimer) {
    clearTimeout(replayTimer);
    replayTimer = null;
  }
}

function openDecisionPanel(panel: "focus" | "intel" | "effects" | "advice") {
  selectedPanel.value = panel;
  decisionDrawerOpen.value = true;
  eventDrawerOpen.value = false;
}

function closeDrawers() {
  eventDrawerOpen.value = false;
  decisionDrawerOpen.value = false;
}
</script>
