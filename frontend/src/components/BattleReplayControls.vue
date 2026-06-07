<template>
  <div class="battle-hex-control-track">
    <div class="stage-control-buttons">
      <button type="button" class="icon-control-btn" title="回到起点" :disabled="!framesLength" @click="$emit('start')">|‹</button>
      <button type="button" class="icon-control-btn" title="上一帧" :disabled="currentTurn <= 0" @click="$emit('backward')">‹</button>
      <button type="button" class="play-control-btn" :disabled="framesLength < 2" @click="$emit('toggle-play')">{{ isPlaying ? "暂停" : "播放" }}</button>
      <button type="button" class="icon-control-btn" title="下一帧" :disabled="currentTurn >= maxFrameIndex" @click="$emit('forward')">›</button>
      <button type="button" class="icon-control-btn" title="跳到最新" :disabled="!framesLength" @click="$emit('latest')">›|</button>
    </div>
    <input :value="currentTurn" class="stage-timeline-slider" :max="maxFrameIndex" min="0" type="range" @input="handleSeek" />
    <div class="stage-speed-row">
      <button v-for="speed in speedOptions" :key="speed" type="button" class="speed-chip" :class="{ active: playbackSpeed === speed }" @click="$emit('speed', speed)">{{ speed }}x</button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  currentTurn: number;
  framesLength: number;
  isPlaying: boolean;
  maxFrameIndex: number;
  playbackSpeed: number;
}>();

const emit = defineEmits<{
  start: [];
  backward: [];
  "toggle-play": [];
  forward: [];
  latest: [];
  seek: [turn: number];
  speed: [speed: number];
}>();

const speedOptions = [0.5, 1, 2, 4];

function handleSeek(event: Event) {
  const target = event.target as HTMLInputElement;
  const turn = Number(target.value);
  if (Number.isFinite(turn)) {
    emit("seek", turn);
  }
}
</script>
