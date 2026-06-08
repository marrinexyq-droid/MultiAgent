<template>
  <div class="app-shell">
    <header v-if="!isBattleRoute" class="topbar">
      <div class="brand-wrap">
        <RouterLink to="/" class="brand">W.</RouterLink>
        <div class="brand-copy">
          <span class="brand-kicker">Agent Evaluation</span>
          <strong>策略评测与可观测平台</strong>
        </div>
      </div>
      <nav class="nav-links">
        <RouterLink to="/history">历史</RouterLink>
        <RouterLink to="/">概览</RouterLink>
        <RouterLink to="/evaluation">评测</RouterLink>
        <RouterLink to="/deployment">场景配置</RouterLink>
        <RouterLink v-if="battleStore.battleId" :to="`/battle/${battleStore.battleId}`">战场</RouterLink>
        <RouterLink v-if="battleStore.battleId" :to="`/review/${battleStore.battleId}`">复盘</RouterLink>
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
