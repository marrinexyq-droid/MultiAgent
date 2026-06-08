<template>
  <main class="page">
    <section class="hero compact">
      <div class="eyebrow">History</div>
      <h1>历史战绩</h1>
      <p>查看已持久化的推演记录，并重新打开完整回放复盘。</p>
      <div class="hero-actions">
        <button class="primary-btn" type="button" :disabled="loading" @click="loadHistory">
          {{ loading ? "加载中" : "刷新历史" }}
        </button>
        <RouterLink class="ghost-btn" to="/deployment">新建推演</RouterLink>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <div>
          <div class="eyebrow">Battle Runs</div>
          <h2>基础历史</h2>
        </div>
      </div>
      <div v-if="error" class="empty-state compact">{{ error }}</div>
      <div v-else-if="loading" class="empty-state compact">正在读取历史记录...</div>
      <div v-else-if="!items.length" class="empty-state compact">暂无历史战绩</div>
      <div v-else class="overview-grid history-grid">
        <article v-for="item in items" :key="item.battle_id" class="meta-card history-card">
          <span>{{ formatDate(item.created_at) }}</span>
          <strong>{{ item.battle_id }}</strong>
          <small>{{ item.mode }} / {{ statusText(item.status) }} / {{ item.frame_count }} 帧</small>
          <div class="history-score-row">
            <span :class="['hud-team', winnerClass(item.winner)]">{{ winnerText(item.winner) }}</span>
            <span>RED {{ formatScore(item.red_score) }}</span>
            <span>BLUE {{ formatScore(item.blue_score) }}</span>
          </div>
          <RouterLink class="ghost-btn compact-btn" :to="`/review/${item.battle_id}`">打开复盘</RouterLink>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { fetchBattleHistory } from "../api";
import type { BattleHistoryItem, TeamKey } from "../types";

const items = ref<BattleHistoryItem[]>([]);
const loading = ref(false);
const error = ref("");

onMounted(() => {
  void loadHistory();
});

async function loadHistory() {
  loading.value = true;
  error.value = "";
  try {
    items.value = await fetchBattleHistory();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "历史记录加载失败";
  } finally {
    loading.value = false;
  }
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function statusText(value: string) {
  const map: Record<string, string> = {
    created: "已创建",
    running: "推演中",
    paused: "已暂停",
    computing: "计算中",
    done: "已完成",
  };
  return map[value] ?? value;
}

function winnerText(value: TeamKey | null) {
  if (value === "red") return "红队胜";
  if (value === "blue") return "蓝队胜";
  return "平局/未结算";
}

function winnerClass(value: TeamKey | null) {
  if (value === "red") return "red";
  if (value === "blue") return "blue";
  return "";
}

function formatScore(value: number | null) {
  return typeof value === "number" ? value.toFixed(2) : "-";
}
</script>
