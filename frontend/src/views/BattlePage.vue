<template>
  <main class="page battle-page" :class="`${battleViewMode}-mode`">
    <section class="battle-statusbar section-card theatre-hud">
      <div class="battle-status-meta battle-status-overview">
        <div class="eyebrow">Theatre HUD</div>
        <strong>Battle {{ battleStore.battleId || "pending" }} · Round {{ roundProgress }}</strong>
        <div class="battle-status-inline battle-status-summary">
          <span>{{ statusLabel }}</span>
          <span>{{ battleStore.mode }}</span>
          <span>Alive {{ aliveUnits }}</span>
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
          class="ghost-btn compact-btn"
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

      <section class="battle-center-stage solo-stage">
        <BattleMap v-model:density="theatreDensity" :frame="battleStore.currentFrame" />
      </section>

      <aside class="battle-side-rail right-rail">
        <InfoColumn :frame="battleStore.currentFrame" />
      </aside>
    </section>

    <section v-else class="battle-theatre-layout">
      <section class="battle-theatre-stage">
        <BattleMap v-model:density="theatreDensity" :frame="battleStore.currentFrame" />
      </section>

      <div class="theatre-event-ticker" @click="eventDrawerOpen = true">
        <span>EVENT</span>
        <strong>{{ latestEventText }}</strong>
      </div>

      <div class="theatre-floating-actions left">
        <button type="button" class="theatre-fab" @click="eventDrawerOpen = true">事件流</button>
      </div>

      <div class="theatre-floating-actions right">
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
import EventFeed from "../components/EventFeed.vue";
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
const aliveUnits = computed(() => battleStore.currentFrame?.units.filter((unit) => unit.alive).length ?? 0);
const showAllEvents = ref(false);
const eventDrawerOpen = ref(false);
const decisionDrawerOpen = ref(false);
const battleViewMode = ref<"theatre" | "analysis">("theatre");
const selectedPanel = ref<"focus" | "intel" | "effects" | "advice">("focus");
const theatreDensity = ref<"fit" | "compact" | "standard" | "expanded">("fit");
let replayTimer: ReturnType<typeof setTimeout> | null = null;
const realtimeActionLabel = computed(() => {
  if (battleStore.status === "running") return "暂停推演";
  if (battleStore.status === "done") return "查看结算";
  if (battleStore.status === "error") return "重新连接推演";
  return "开始实时推演";
});
const realtimeActionDisabled = computed(() => battleStore.status === "running");
const realtimeActionHint = computed(() => {
  if (battleStore.status === "running") return "当前前端尚未接入暂停接口，先以状态占位展示。";
  if (battleStore.status === "done") return "跳转结算查看完整复盘。";
  return "开始实时推演";
});
const latestEventText = computed(() => {
  const event = battleStore.currentFrame?.events_structured?.at(-1);
  if (event) return event.summary;
  return "等待战术事件写入";
});
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

function eventHeadline(event: { type: string; actor_id?: string | null }) {
  const actor = event.actor_id ? ` ${event.actor_id}` : "";
  return `[${event.type.toUpperCase()}]${actor}`;
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
