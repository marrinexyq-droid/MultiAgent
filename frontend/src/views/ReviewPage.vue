<template>
  <main class="page">
    <section class="hero compact">
      <div class="eyebrow">Review</div>
      <h1>结算复盘</h1>
      <p>查看回放帧、团队评分、功勋与情报结果。</p>
      <div class="hero-actions">
        <button class="primary-btn" @click="loadReplay">载入回放</button>
        <RouterLink v-if="battleStore.battleId" class="ghost-btn" :to="`/battle/${battleStore.battleId}`">返回战场</RouterLink>
      </div>
    </section>
    <section class="section-card">
      <div class="section-head">
        <div><div class="eyebrow">Replay</div><h2>回放控制</h2></div>
      </div>
      <div class="timeline-row">
        <button class="ghost-btn" type="button" @click="seekToStart" :disabled="!battleStore.frames.length">起点</button>
        <input
          v-if="battleStore.frames.length"
          v-model="battleStore.currentTurn"
          class="timeline-slider"
          :max="Math.max(0, battleStore.frames.length - 1)"
          min="0"
          type="range"
        />
        <div v-else class="empty-state compact">等待回放帧…</div>
        <button class="ghost-btn" type="button" @click="seekToLatest" :disabled="!battleStore.frames.length">最新</button>
      </div>
      <div class="timeline-meta">
        <span>ROUND / {{ battleStore.currentTurn }}</span>
        <span>FRAMES / {{ battleStore.frames.length }}</span>
        <span>STATE / {{ battleStore.status }}</span>
      </div>
    </section>
    <div class="review-layout">
      <BattleMap :frame="battleStore.currentFrame" />
      <section class="section-card review-settlement-card">
        <div class="section-head">
          <div><div class="eyebrow">Summary</div><h2>结算信息</h2></div>
        </div>
        <template v-if="resultView">
          <div class="review-summary-grid">
            <div class="meta-card">
              <span>获胜方</span>
              <strong>{{ winnerText(resultView.winner) }}</strong>
            </div>
            <div class="meta-card">
              <span>原因</span>
              <strong>{{ reasonText(resultView.reason) }}</strong>
            </div>
            <div class="meta-card">
              <span>回合数</span>
              <strong>{{ resultView.turn ?? "-" }}</strong>
            </div>
            <div class="meta-card">
              <span>主导胜因</span>
              <strong>{{ reasonText(resultView.dominant_reason) }}</strong>
            </div>
            <div class="meta-card team-red-soft">
              <span>红队总分</span>
              <strong>{{ formatScore(resultView.red_score) }}</strong>
            </div>
            <div class="meta-card team-blue-soft">
              <span>蓝队总分</span>
              <strong>{{ formatScore(resultView.blue_score) }}</strong>
            </div>
          </div>

          <div class="review-sections">
            <div class="section-card inner-card">
              <div class="section-head compact-head">
                <div><div class="eyebrow">Breakdown</div><h2>评分分解</h2></div>
              </div>
              <div class="review-score-grid single-column">
                <div class="score-board team-red-soft">
                  <div class="score-board-head">
                    <div>
                      <div class="eyebrow">RED</div>
                      <h3>红队分解卡</h3>
                    </div>
                    <div class="score-board-total">{{ formatScore(resultView.red_score) }}</div>
                  </div>
                  <div class="score-board-body">
                    <div v-for="(value, key) in resultView.score_breakdown?.red ?? {}" :key="`red-${key}`" class="score-row-vue">
                      <span>{{ metricLabel(key) }}</span>
                      <div class="score-inline">
                        <div class="score-bar"><div class="score-bar-fill team-red-fill" :style="{ width: scoreBarWidth(value) }" /></div>
                        <strong>{{ formatScore(value) }}</strong>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="score-board team-blue-soft">
                  <div class="score-board-head">
                    <div>
                      <div class="eyebrow">BLUE</div>
                      <h3>蓝队分解卡</h3>
                    </div>
                    <div class="score-board-total">{{ formatScore(resultView.blue_score) }}</div>
                  </div>
                  <div class="score-board-body">
                    <div v-for="(value, key) in resultView.score_breakdown?.blue ?? {}" :key="`blue-${key}`" class="score-row-vue">
                      <span>{{ metricLabel(key) }}</span>
                      <div class="score-inline">
                        <div class="score-bar"><div class="score-bar-fill team-blue-fill" :style="{ width: scoreBarWidth(value) }" /></div>
                        <strong>{{ formatScore(value) }}</strong>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="section-card inner-card">
              <div class="section-head compact-head">
                <div><div class="eyebrow">Merit</div><h2>功勋榜</h2></div>
              </div>
              <template v-if="meritEntries.length">
                <div v-if="topMerits[0]" class="merit-hero-lead">
                  <div class="merit-hero-card rank-1 lead">
                    <div class="eyebrow">TOP 1</div>
                    <div class="merit-agent">{{ topMerits[0][0] }}</div>
                    <p>{{ roleText(topMerits[0][1].role) }} / {{ (topMerits[0][1].commendations ?? []).join(' · ') || '常规贡献' }}</p>
                    <p>{{ topMerits[0][1].explanation }}</p>
                    <div class="merit-score">功勋 {{ formatScore(topMerits[0][1].merit_score) }}</div>
                  </div>
                </div>
                <div v-if="topMerits.length > 1" class="merit-side-grid">
                  <div
                    v-for="([agentId, merit], index) in topMerits.slice(1)"
                    :key="`top-side-${agentId}`"
                    class="merit-hero-card"
                    :class="`rank-${index + 2}`"
                  >
                    <div class="eyebrow">TOP {{ index + 2 }}</div>
                    <div class="merit-agent">{{ agentId }}</div>
                    <p>{{ roleText(merit.role) }} / {{ (merit.commendations ?? []).join(' · ') || '常规贡献' }}</p>
                    <p>{{ summarizeExplanation(merit.explanation) }}</p>
                    <div class="merit-score">功勋 {{ formatScore(merit.merit_score) }}</div>
                  </div>
                </div>
                <div v-if="remainingMerits.length" class="list-stack compact merit-list-rest">
                  <div v-for="([agentId, merit], index) in remainingMerits" :key="`rest-${agentId}`" class="stack-card merit-row-card">
                    <div class="stack-title">#{{ index + 4 }} · {{ agentId }}</div>
                    <p>{{ roleText(merit.role) }} / {{ summarizeExplanation(merit.explanation) }}</p>
                    <small>功勋 {{ formatScore(merit.merit_score) }}</small>
                  </div>
                </div>
              </template>
              <div v-else class="empty-state">暂无功勋信息</div>
            </div>

            <div class="section-card inner-card">
              <div class="section-head compact-head">
                <div><div class="eyebrow">Turning Points</div><h2>关键转折</h2></div>
              </div>
              <div v-if="turningPoints.length" class="list-stack compact">
                <div v-for="(item, index) in turningPoints" :key="`${item.turn}-${item.type}-${index}`" class="stack-card merit-row-card">
                  <div class="event-meta">
                    <span>T{{ item.turn }}</span>
                    <span :class="['event-type', String(item.type).toLowerCase()]">{{ item.type }}</span>
                  </div>
                  <p>{{ item.summary }}</p>
                  <small>{{ item.actor_id || item.target_id || "系统事件" }}</small>
                </div>
              </div>
              <div v-else class="empty-state">暂无关键转折</div>
            </div>
          </div>
        </template>
        <div v-else class="empty-state">先载入回放后，这里会显示结算信息。</div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import BattleMap from "../components/BattleMap.vue";
import { useBattleStore } from "../stores/battle";

const props = defineProps<{ id: string }>();
const battleStore = useBattleStore();

if (!battleStore.battleId) {
  battleStore.battleId = props.id;
}

const resultView = computed(() => {
  const summary = battleStore.summary as Record<string, any> | null;
  if (!summary) return null;
  return summary.result ? summary.result : summary;
});

const meritEntries = computed(() => {
  const result = resultView.value;
  if (!result?.agent_merits) return [];
  return Object.entries(result.agent_merits) as Array<[string, any]>;
});
const topMerits = computed(() => meritEntries.value.slice(0, 3));
const remainingMerits = computed(() => meritEntries.value.slice(3));
const turningPoints = computed(() => {
  const result = resultView.value;
  return Array.isArray(result?.key_turning_points) ? result.key_turning_points : [];
});

async function loadReplay() {
  await battleStore.loadReplay();
}

function seekToStart() {
  battleStore.currentTurn = 0;
}

function seekToLatest() {
  battleStore.currentTurn = Math.max(0, battleStore.frames.length - 1);
}

function winnerText(value: string | null | undefined) {
  if (value === "red") return "红队";
  if (value === "blue") return "蓝队";
  return "平局";
}

function reasonText(value: string | null | undefined) {
  const map: Record<string, string> = {
    red_eliminated: "红队全部失效",
    blue_eliminated: "蓝队全部失效",
    stalemate_adjudication: "僵局裁决",
    elimination_score: "减员压制占优",
    survival_score: "生存表现占优",
    objective_score: "目标控制占优",
    initiative_score: "态势主动性占优",
    coordination_score: "协同质量占优",
    draw: "平局",
  };
  return value ? map[value] ?? value : "-";
}

function metricLabel(value: string) {
  const map: Record<string, string> = {
    elimination_score: "减员压制",
    survival_score: "生存保持",
    objective_score: "目标控制",
    initiative_score: "态势主动",
    coordination_score: "协同质量",
  };
  return map[value] ?? value;
}

function roleText(value: string) {
  const map: Record<string, string> = {
    coordinator: "协调",
    scout: "侦察",
    attacker: "攻击手",
    defender: "防御手",
    support: "支援",
    jammer: "干扰",
    controller: "控制",
    assaulter: "突击",
  };
  return map[value] ?? value;
}

function formatScore(value: unknown) {
  return typeof value === "number" ? value.toFixed(2) : "-";
}

function scoreBarWidth(value: unknown) {
  if (typeof value !== "number") return "0%";
  return `${Math.max(8, Math.min(100, value * 100))}%`;
}

function summarizeExplanation(value: string | undefined) {
  if (!value) return "暂无解释";
  return value.length > 48 ? `${value.slice(0, 48)}...` : value;
}
</script>
