<template>
  <Teleport to="body">
    <div v-if="open" class="overlay-backdrop" @click="$emit('close')">
      <section class="overlay-panel" @click.stop>
        <div class="overlay-panel-head">
          <div>
            <div v-if="eyebrow" class="eyebrow">{{ eyebrow }}</div>
            <h2>{{ title }}</h2>
          </div>
          <button type="button" class="ghost-btn compact-btn" @click="$emit('close')">关闭</button>
        </div>
        <div class="overlay-panel-body">
          <slot />
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";

defineProps<{
  open: boolean;
  title: string;
  eyebrow?: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
}>();

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") {
    emit("close");
  }
}

onMounted(() => {
  window.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
});
</script>
