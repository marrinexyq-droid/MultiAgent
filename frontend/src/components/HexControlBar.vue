<template>
  <div class="hex-control-bar">
    <div class="hex-control-buttons">
      <button type="button" @click="$emit('start')">|‹</button>
      <button type="button" @click="$emit('prev')">‹</button>
      <button type="button" class="hex-play" @click="$emit('toggle')">{{ playing ? "暂停" : "播放" }}</button>
      <button type="button" @click="$emit('next')">›</button>
      <button type="button" @click="$emit('latest')">›|</button>
    </div>
    <input
      class="hex-range"
      type="range"
      min="0"
      :max="maxIndex"
      :value="currentIndex"
      @input="$emit('seek', Number(($event.target as HTMLInputElement).value))"
    />
    <div class="hex-speed-group">
      <button
        v-for="speed in speeds"
        :key="speed"
        type="button"
        :class="{ active: playbackSpeed === speed }"
        @click="$emit('speed', speed)"
      >
        {{ speed }}x
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  currentIndex: number;
  maxIndex: number;
  playing: boolean;
  playbackSpeed: number;
}>();

defineEmits<{
  start: [];
  prev: [];
  toggle: [];
  next: [];
  latest: [];
  seek: [index: number];
  speed: [speed: number];
}>();

const speeds = [0.5, 1, 2, 4];
</script>
