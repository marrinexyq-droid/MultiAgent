<template>
  <div class="ring-gauge">
    <svg class="ring-svg" :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`">
      <circle
        class="ring-bg"
        :cx="center" :cy="center" :r="radius"
        fill="none"
        :stroke-width="strokeW"
      />
      <circle
        class="ring-fill"
        :cx="center" :cy="center" :r="radius"
        fill="none"
        :stroke-width="strokeW"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="offset"
        stroke-linecap="round"
        :style="{ stroke: color }"
      />
      <text class="ring-value" :x="center" :y="center - 2" text-anchor="middle" dominant-baseline="central" :fill="color">{{ value }}%</text>
      <text class="ring-label" :x="center" :y="center + 12" text-anchor="middle" dominant-baseline="central" fill="var(--hex-text-muted)">{{ label }}</text>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(defineProps<{
  value: number;
  label: string;
  color?: string;
  size?: number;
}>(), {
  color: "var(--hex-accent)",
  size: 72,
});

const center = computed(() => props.size / 2);
const radius = computed(() => (props.size / 2) - 8);
const strokeW = computed(() => Math.max(4, props.size / 12));
const circumference = computed(() => 2 * Math.PI * radius.value);
const offset = computed(() => circumference.value * (1 - Math.max(0, Math.min(100, props.value)) / 100));
</script>

<style scoped>
.ring-gauge {
  display: flex;
  align-items: center;
  justify-content: center;
}
.ring-bg {
  stroke: rgba(255,255,255,0.04);
}
.ring-fill {
  transition: stroke-dashoffset 0.6s ease-out, stroke 0.3s ease;
  filter: drop-shadow(0 0 4px currentColor);
}
.ring-value {
  font-size: 14px;
  font-weight: 800;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.ring-label {
  font-size: 8px;
  font-weight: 600;
  font-family: var(--font-mono);
  letter-spacing: 0.04em;
}
</style>
