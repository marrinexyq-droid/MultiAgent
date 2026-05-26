<template>
  <Transition name="dmg-float">
    <div
      v-if="visible"
      class="dmg-number"
      :class="`dmg-${type}`"
      :style="{ left: x + 'px', top: y + 'px' }"
    >
      {{ prefix }}{{ value }}
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

const props = withDefaults(
  defineProps<{
    x: number;
    y: number;
    value: number;
    type?: string;
    duration?: number;
  }>(),
  { type: "damage", duration: 900 }
);

const visible = ref(true);
const prefix = props.type === "heal" ? "+" : "";

onMounted(() => {
  setTimeout(() => {
    visible.value = false;
  }, props.duration);
});
</script>

<style scoped>
.dmg-number {
  position: absolute;
  z-index: 50;
  font-size: 18px;
  font-weight: 900;
  pointer-events: none;
  text-shadow: 0 2px 8px rgba(0,0,0,0.6), 0 0 4px rgba(0,0,0,0.4);
  transform: translate(-50%, -50%);
  font-variant-numeric: tabular-nums;
  color: #ef4444;
}
.dmg-heal { color: #4ade80; }
.dmg-immune { color: #a855f7; }

.dmg-float-enter-active {
  transition: all 0.8s ease-out;
}
.dmg-float-leave-active {
  transition: opacity 0.2s ease-in;
}
.dmg-float-enter-from {
  opacity: 0;
  transform: translate(-50%, 0%);
}
.dmg-float-enter-to {
  opacity: 1;
  transform: translate(-50%, -30px);
}
.dmg-float-leave-to {
  opacity: 0;
}
</style>
