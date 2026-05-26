<template>
  <svg class="hex-3d-bg" viewBox="0 0 78 88" aria-hidden="true">
    <!-- Base fill -->
    <polygon points="39,0 77,22 77,66 39,88 1,66 1,22" :fill="fillColor" />

    <!-- Top highlight -->
    <polygon points="39,0 77,22 39,44 1,22" fill="rgba(255,255,255,0.06)" />

    <!-- Bottom shadow -->
    <polygon points="39,44 77,66 39,88 1,66" fill="rgba(0,0,0,0.12)" />

    <!-- Top edge highlight line -->
    <line x1="1" y1="22" x2="39" y2="0" stroke="rgba(255,255,255,0.08)" stroke-width="2" />
    <line x1="39" y1="0" x2="77" y2="22" stroke="rgba(255,255,255,0.06)" stroke-width="1.5" />

    <!-- Bottom edge shadow line -->
    <line x1="1" y1="66" x2="39" y2="88" stroke="rgba(0,0,0,0.2)" stroke-width="2" />
    <line x1="39" y1="88" x2="77" y2="66" stroke="rgba(0,0,0,0.15)" stroke-width="1.5" />

    <!-- Terrain feature icon (varied by seed) -->
    <g v-if="type === 'forest'" :transform="`translate(27,48)`">
      <template v-if="v === 0">
        <path d="M12 2L6 12h4v8h4v-8h4L12 2z" fill="#2d6a2d" opacity="0.9"/>
        <rect x="11" y="16" width="2" height="6" fill="#5c3a1e" opacity="0.7"/>
        <circle cx="20" cy="12" r="6" fill="#3a8a2d" opacity="0.5"/>
      </template>
      <template v-else-if="v === 1">
        <path d="M12 2L6 12h4v8h4v-8h4L12 2z" fill="#1d5a1d" opacity="0.9"/>
        <rect x="11" y="16" width="2" height="6" fill="#4a2a1a" opacity="0.7"/>
        <path d="M8 14L20 8" stroke="#3a7a2d" stroke-width="3" opacity="0.4" stroke-linecap="round"/>
      </template>
      <template v-else>
        <path d="M10 4L6 12h3v8h2v-8h3l-4-8z" fill="#2a6a2a" opacity="0.85"/>
        <rect x="10" y="16" width="1.5" height="6" fill="#5c3a1e" opacity="0.6"/>
        <circle cx="15" cy="10" r="5" fill="#3a8a3a" opacity="0.35"/>
      </template>
    </g>
    <g v-else-if="type === 'mountain'" :transform="`translate(27,48)`">
      <template v-if="v === 0">
        <path d="M2 22L8 8l5 8h-2l3 6H2z" fill="#8a7a62" opacity="0.8"/>
        <path d="M10 22l5-10 6 10H10z" fill="#9a8a72" opacity="0.7"/>
      </template>
      <template v-else>
        <path d="M4 20L8 10l4 8h-2l3 6H4z" fill="#7a6a52" opacity="0.75"/>
        <path d="M12 22l4-8 5 8H12z" fill="#8a7a62" opacity="0.6"/>
        <path d="M6 14l3-6 3 6" stroke="#9a8a72" stroke-width="1" opacity="0.5"/>
      </template>
    </g>
    <g v-else-if="type === 'water'" :transform="`translate(27,48)`">
      <path d="M2 14Q6 10 12 14T22 14" fill="none" stroke="#3a7a9a" stroke-width="2" opacity="0.7"/>
      <path d="M2 18Q6 14 12 18T22 18" fill="none" stroke="#3a7a9a" stroke-width="2" opacity="0.5"/>
      <circle v-if="v === 0" cx="8" cy="10" r="1.5" fill="rgba(255,255,255,0.15)"/>
      <circle v-else cx="14" cy="20" r="1.5" fill="rgba(255,255,255,0.1)"/>
    </g>
    <g v-else-if="type === 'urban'" :transform="`translate(27,48)`">
      <rect x="7" y="5" width="10" height="14" fill="#7a6a5a" opacity="0.7"/>
      <path d="M6 5l6-3 6 3" fill="none" stroke="#7a6a5a" stroke-width="1.5" opacity="0.7"/>
      <rect x="10" y="12" width="4" height="7" fill="#5a4a3a" opacity="0.5"/>
      <rect v-if="v === 0" x="9" y="7" width="2" height="2" fill="rgba(255,200,100,0.3)"/>
      <rect v-else x="12" y="9" width="2" height="2" fill="rgba(255,200,100,0.3)"/>
    </g>
    <g v-else-if="type === 'road'" :transform="`translate(27,48)`">
      <line x1="4" y1="8" x2="20" y2="8" stroke="#8a7a62" stroke-width="2" stroke-dasharray="3 4" opacity="0.6"/>
      <line x1="4" y1="14" x2="20" y2="14" stroke="#8a7a62" stroke-width="2" stroke-dasharray="3 4" opacity="0.6"/>
      <line v-if="v === 0" x1="4" y1="11" x2="20" y2="11" stroke="rgba(200,180,120,0.15)" stroke-width="1"/>
    </g>
    <g v-else-if="type === 'rough'" :transform="`translate(27,48)`">
      <circle cx="10" cy="10" r="2" fill="#9a8a6a" opacity="0.7"/>
      <circle cx="16" cy="8" r="1.5" fill="#9a8a6a" opacity="0.6"/>
      <circle cx="8" cy="16" r="1.5" fill="#9a8a6a" opacity="0.6"/>
      <template v-if="v === 0"><circle cx="14" cy="16" r="1" fill="#8a7a5a" opacity="0.5"/></template>
      <template v-else><circle cx="6" cy="12" r="1" fill="#8a7a5a" opacity="0.5"/></template>
    </g>
    <g v-else-if="type === 'marsh'" :transform="`translate(27,48)`">
      <path d="M8 6v12M12 4v14M16 8v10" stroke="#4a7a4a" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
      <circle v-if="v === 0" cx="10" cy="18" r="2" fill="rgba(50,120,50,0.3)"/>
      <circle v-else cx="16" cy="16" r="2" fill="rgba(50,120,50,0.3)"/>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ type: string; x?: number; y?: number }>();

const COLORS: Record<string, string> = {
  open: "#7a7a6a", road: "#8a887a", forest: "#4a9a4a",
  urban: "#6a5a4a", water: "#2a7a9a", rough: "#7a6a4a",
  marsh: "#4a7a4a", mountain: "#7a6a5a",
};

const fillColor = computed(() => COLORS[props.type] ?? "#7a7a6a");
const v = computed(() => {
  const seed = (props.x ?? 0) * 7 + (props.y ?? 0) * 13;
  return Math.abs(seed) % 3;
});
</script>

<style scoped>
.hex-3d-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  display: block;
}
</style>
