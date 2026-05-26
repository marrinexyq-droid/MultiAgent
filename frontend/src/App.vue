<template>
  <div class="app-shell">
    <header v-if="!isBattleRoute" class="topbar">
      <div class="brand-wrap">
        <RouterLink to="/" class="brand">W.</RouterLink>
        <div class="brand-copy">
          <span class="brand-kicker">Multi-Agent Theatre</span>
          <strong>对抗推演平台</strong>
        </div>
      </div>
      <nav class="nav-links">
        <RouterLink to="/">大厅</RouterLink>
        <RouterLink to="/deployment">部署</RouterLink>
        <RouterLink to="/hex-lab">六边形</RouterLink>
        <RouterLink to="/fantasy">魔幻</RouterLink>
        <RouterLink v-if="battleStore.battleId" :to="`/battle/${battleStore.battleId}`">战场</RouterLink>
        <RouterLink v-if="battleStore.battleId" :to="`/review/${battleStore.battleId}`">结算</RouterLink>
      </nav>
    </header>
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView } from "vue-router";
import { useRoute } from "vue-router";
import { useBattleStore } from "./stores/battle";

const battleStore = useBattleStore();
const route = useRoute();
const isBattleRoute = computed(() => route.path.startsWith("/battle/"));
</script>
