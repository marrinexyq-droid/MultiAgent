<template>
  <aside class="section-card event-feed-panel">
    <div class="section-head compact-head">
      <div>
        <div class="eyebrow">Event Feed</div>
        <h2 class="rail-title">战术事件流</h2>
      </div>
      <button type="button" class="ghost-btn compact-btn rail-action-btn" @click="$emit('openArchive')">归档</button>
    </div>

    <div class="event-filter-row">
      <button
        v-for="filter in filters"
        :key="filter.value"
        type="button"
        class="event-filter-chip"
        :class="{ active: activeFilter === filter.value }"
        @click="activeFilter = filter.value"
      >
        {{ filter.label }}
      </button>
    </div>

    <div v-if="pinnedEvent" class="pinned-event-card" @click="focusEvent(pinnedEvent)">
      <span class="event-pin-label">KEY EVENT</span>
      <strong>{{ eventHeadline(pinnedEvent) }}</strong>
      <p>{{ pinnedEvent.summary }}</p>
    </div>

    <div v-if="filteredEvents.length" class="timeline-event-list event-feed-list">
      <button
        v-for="(event, index) in filteredEvents"
        :key="`${event.turn}-${index}-${event.type}-${event.actor_id ?? event.target_id ?? 'event'}`"
        type="button"
        class="timeline-event-item event-feed-item"
        :class="[event.type.toLowerCase(), { active: event.turn === battleStore.currentTurn }]"
        @click="focusEvent(event)"
      >
        <span class="timeline-event-turn">T{{ event.turn }}</span>
        <div>
          <div class="event-feed-meta">
            <strong>{{ eventHeadline(event) }}</strong>
            <span v-if="event.team" :class="['event-team-chip', event.team]">{{ event.team }}</span>
          </div>
          <p>{{ event.summary }}</p>
        </div>
      </button>
    </div>
    <div v-else class="empty-state compact">暂无匹配事件</div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useBattleStore } from "../stores/battle";
import type { BattleFrame, TeamKey } from "../types";

type EventFilter = "all" | "system" | TeamKey | "risk";
type StructuredEvent = BattleFrame["events_structured"][number];

const props = defineProps<{ frame: BattleFrame | null }>();
defineEmits<{ openArchive: [] }>();

const battleStore = useBattleStore();
const activeFilter = ref<EventFilter>("all");
const filters: Array<{ label: string; value: EventFilter }> = [
  { label: "全部", value: "all" },
  { label: "系统", value: "system" },
  { label: "红方", value: "red" },
  { label: "蓝方", value: "blue" },
  { label: "风险", value: "risk" },
];
const riskTypes = new Set(["RISK", "SPOT", "JAM", "BLOCK", "ENGAGE", "RESULT"]);

const events = computed(() => (props.frame?.events_structured ?? []).slice().reverse());
const filteredEvents = computed(() => {
  return events.value.filter((event) => {
    if (activeFilter.value === "all") return true;
    if (activeFilter.value === "system") return !event.team;
    if (activeFilter.value === "risk") return riskTypes.has(event.type.toUpperCase()) || event.markers.some((marker) => riskTypes.has(marker.toUpperCase()));
    return event.team === activeFilter.value;
  });
});
const pinnedEvent = computed(() => events.value.find((event) => riskTypes.has(event.type.toUpperCase())) ?? events.value[0]);

function focusEvent(event: StructuredEvent) {
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

function eventHeadline(event: StructuredEvent) {
  const actor = event.actor_id ? ` · ${event.actor_id}` : "";
  return `${event.type.toUpperCase()}${actor}`;
}
</script>
