<template>
  <main class="page evaluation-page">
    <section class="hero compact evaluation-hero">
      <div>
        <div class="eyebrow">Agent Evaluation</div>
        <h1>策略评测仪表盘</h1>
        <p>用确定性场景对比多智能体策略，跟踪胜率、任务完成率、无效行动率和 LLM 决策观测指标。</p>
      </div>
      <div class="hero-actions">
        <button class="primary-btn" :disabled="loading" @click="loadReport">{{ loading ? "读取中" : "刷新报告" }}</button>
        <RouterLink class="ghost-btn" to="/deployment">配置新场景</RouterLink>
      </div>
    </section>

    <section v-if="error" class="section-card error-card">
      <div class="section-head">
        <div><div class="eyebrow">Report</div><h2>评测报告不可用</h2></div>
      </div>
      <p>{{ error }}</p>
      <p>先运行 <code>python -m src.battle.eval_runner --runs 20</code> 生成最新报告。</p>
    </section>

    <template v-else-if="report">
      <section class="section-card evaluation-overview">
        <div class="section-head">
          <div>
            <div class="eyebrow">Latest Report</div>
            <h2>最新评测概览</h2>
          </div>
          <div class="phase-chip ghost">{{ generatedAt }}</div>
        </div>
        <div class="overview-grid">
          <div class="meta-card">
            <span>策略数</span>
            <strong>{{ report.policies.length }}</strong>
            <small>{{ report.policies.join(" / ") }}</small>
          </div>
          <div class="meta-card">
            <span>场景数</span>
            <strong>{{ report.scenarios.length }}</strong>
            <small>{{ report.scenarios.join(" / ") }}</small>
          </div>
          <div class="meta-card">
            <span>每场景运行</span>
            <strong>{{ report.runs_per_scenario }}</strong>
            <small>Seed {{ report.seed }}</small>
          </div>
          <div class="meta-card">
            <span>总运行数</span>
            <strong>{{ report.runs.length }}</strong>
            <small>自动化仿真样本</small>
          </div>
        </div>
      </section>

      <section class="evaluation-policy-grid">
        <article v-for="policy in policyRows" :key="policy.name" class="section-card policy-card">
          <div class="section-head compact-head">
            <div>
              <div class="eyebrow">Policy</div>
              <h2>{{ policy.name }}</h2>
            </div>
            <div class="policy-win-rate">{{ percent(policy.overall.red_win_rate) }}</div>
          </div>
          <div class="focus-metric-grid compact">
            <div class="mini-metric"><span>红方胜率</span><strong>{{ percent(policy.overall.red_win_rate) }}</strong></div>
            <div class="mini-metric"><span>蓝方胜率</span><strong>{{ percent(policy.overall.blue_win_rate) }}</strong></div>
            <div class="mini-metric"><span>任务完成</span><strong>{{ percent(policy.overall.avg_task_completion_rate) }}</strong></div>
            <div class="mini-metric"><span>无效行动</span><strong>{{ percent(policy.overall.avg_invalid_action_rate) }}</strong></div>
          </div>
          <div class="evaluation-bars">
            <div class="score-row-vue">
              <span>平均红方分</span>
              <div class="score-inline">
                <div class="score-bar"><div class="score-bar-fill team-red-fill" :style="{ width: scoreWidth(policy.overall.avg_red_score) }" /></div>
                <strong>{{ score(policy.overall.avg_red_score) }}</strong>
              </div>
            </div>
            <div class="score-row-vue">
              <span>平均蓝方分</span>
              <div class="score-inline">
                <div class="score-bar"><div class="score-bar-fill team-blue-fill" :style="{ width: scoreWidth(policy.overall.avg_blue_score) }" /></div>
                <strong>{{ score(policy.overall.avg_blue_score) }}</strong>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section class="section-card">
        <div class="section-head">
          <div><div class="eyebrow">Scenario Breakdown</div><h2>场景分解</h2></div>
        </div>
        <div class="evaluation-table-wrap">
          <table class="evaluation-table">
            <thead>
              <tr>
                <th>策略</th>
                <th>场景</th>
                <th>运行</th>
                <th>红方胜率</th>
                <th>任务完成</th>
                <th>无效行动</th>
                <th>侦察情报使用</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in scenarioRows" :key="`${row.policy}-${row.scenario}`">
                <td>{{ row.policy }}</td>
                <td>{{ row.scenario }}</td>
                <td>{{ row.metrics.runs }}</td>
                <td>{{ percent(row.metrics.red_win_rate) }}</td>
                <td>{{ percent(row.metrics.avg_task_completion_rate) }}</td>
                <td>{{ percent(row.metrics.avg_invalid_action_rate) }}</td>
                <td>{{ fixed(row.metrics.avg_scout_reports_used) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="section-card">
        <div class="section-head">
          <div><div class="eyebrow">Recent Runs</div><h2>运行样本</h2></div>
        </div>
        <div class="list-stack compact evaluation-run-list">
          <div v-for="run in recentRuns" :key="`${run.policy}-${run.scenario}-${run.seed}`" class="stack-card evaluation-run-card">
            <div class="stack-title">{{ run.policy }} / {{ run.scenario }}</div>
            <p>Winner {{ winnerLabel(run.winner) }} · Turns {{ run.turns }} · Reason {{ run.reason || "-" }}</p>
            <small>Task {{ percent(run.task_completion_rate) }} / Invalid {{ percent(run.invalid_action_rate) }} / Scout reports {{ run.scout_reports_used }}</small>
          </div>
        </div>
      </section>
    </template>

    <section v-else class="section-card">
      <div class="empty-state">正在读取最新评测报告...</div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { fetchLatestEvaluation } from "../api";
import type { EvaluationMetrics, EvaluationReport, TeamKey } from "../types";

const report = ref<EvaluationReport | null>(null);
const loading = ref(false);
const error = ref("");

onMounted(loadReport);

const generatedAt = computed(() => {
  if (!report.value?.generated_at) return "-";
  return report.value.generated_at.replace("T", " ").replace("Z", " UTC");
});

const policyRows = computed(() => {
  if (!report.value) return [];
  return Object.entries(report.value.summary).map(([name, payload]) => ({
    name,
    overall: payload.overall,
    byScenario: payload.by_scenario,
  }));
});

const scenarioRows = computed<Array<{ policy: string; scenario: string; metrics: EvaluationMetrics }>>(() => {
  if (!report.value) return [];
  return Object.entries(report.value.summary).flatMap(([policy, payload]) =>
    Object.entries(payload.by_scenario).map(([scenario, metrics]) => ({ policy, scenario, metrics })),
  );
});

const recentRuns = computed(() => report.value?.runs.slice(-8).reverse() ?? []);

async function loadReport() {
  loading.value = true;
  error.value = "";
  try {
    report.value = await fetchLatestEvaluation();
  } catch (err) {
    report.value = null;
    error.value = err instanceof Error ? err.message : "评测报告读取失败";
  } finally {
    loading.value = false;
  }
}

function percent(value: number | null | undefined) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "-";
}

function score(value: number | null | undefined) {
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function fixed(value: number | null | undefined) {
  return typeof value === "number" ? value.toFixed(2) : "-";
}

function scoreWidth(value: number | null | undefined) {
  const bounded = Math.max(0, Math.min(1, value ?? 0));
  return `${Math.round(bounded * 100)}%`;
}

function winnerLabel(winner: TeamKey | null) {
  if (winner === "red") return "RED";
  if (winner === "blue") return "BLUE";
  return "DRAW";
}
</script>
