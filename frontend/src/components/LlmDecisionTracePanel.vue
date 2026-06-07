<template>
  <section class="section-card llm-trace-panel">
    <div class="section-head compact-head">
      <div>
        <div class="eyebrow">LLM Trace</div>
        <h2 class="rail-title">决策追踪</h2>
      </div>
      <div v-if="frame" class="phase-chip ghost">T{{ frame.turn }}</div>
    </div>

    <div v-if="!frame" class="empty-state compact">载入战斗帧后，可检查每个智能体的 LLM 决策记录。</div>
    <div v-else-if="!frame.llm_mode_enabled" class="empty-state compact">
      当前回合为规则策略运行，没有 LLM 延迟、兜底原因或 token 用量记录。
    </div>
    <template v-else>
      <div class="focus-metric-grid compact llm-trace-summary">
        <div class="mini-metric"><span>决策数</span><strong>{{ traceSummary.count }}</strong></div>
        <div class="mini-metric"><span>平均延迟</span><strong>{{ formatLatency(traceSummary.avgLatency) }}</strong></div>
        <div class="mini-metric"><span>总 Token</span><strong>{{ formatTokens(traceSummary.totalTokens) }}</strong></div>
        <div class="mini-metric"><span>兜底</span><strong>{{ traceSummary.fallbacks }}</strong></div>
      </div>

      <div v-if="!visibleTraces.length" class="empty-state compact">
        {{ emptyTraceText }}
      </div>
      <div v-else class="list-stack compact llm-trace-list">
        <div v-for="trace in visibleTraces" :key="`${trace.turn}-${trace.agent_id}`" class="stack-card llm-trace-card">
          <div class="llm-trace-head">
            <div>
              <div class="stack-title">{{ trace.agent_id }}</div>
              <small>{{ teamLabel(trace.team) }} / {{ roleLabel(trace.role) }} / {{ actionLabel(trace.decision_action_type) }}</small>
            </div>
            <span class="llm-trace-status" :class="{ fallback: !trace.ok }">{{ trace.ok ? "成功" : "兜底" }}</span>
          </div>

          <div class="focus-metric-grid compact llm-trace-metrics">
            <div class="mini-metric"><span>延迟</span><strong>{{ formatLatency(trace.latency_ms) }}</strong></div>
            <div class="mini-metric"><span>Prompt</span><strong>{{ formatTokens(trace.prompt_tokens) }}</strong></div>
            <div class="mini-metric"><span>Completion</span><strong>{{ formatTokens(trace.completion_tokens) }}</strong></div>
            <div class="mini-metric"><span>总计</span><strong>{{ formatTokens(trace.total_tokens) }}</strong></div>
          </div>

          <p class="llm-fallback-reason">
            兜底原因：{{ fallbackLabel(trace.fallback_reason) }}
          </p>
          <details v-if="trace.raw_completion || trace.llm_error" class="llm-raw-trace">
            <summary>原始输出</summary>
            <pre v-if="trace.raw_completion">{{ trace.raw_completion }}</pre>
            <p v-if="trace.llm_error">调用信息：{{ trace.llm_error }}</p>
          </details>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { BattleFrame, RoleKey, TeamKey } from "../types";

type LlmDecisionTrace = NonNullable<BattleFrame["llm_decision_traces"]>[number];

const props = defineProps<{
  frame: BattleFrame | null;
  focusedAgentId?: string;
  limit?: number;
}>();

const visibleTraces = computed(() => {
  const traces = props.frame?.llm_decision_traces ?? [];
  const filtered = props.focusedAgentId
    ? traces.filter((trace) => trace.agent_id === props.focusedAgentId)
    : traces;
  return filtered.slice(0, props.limit ?? 6);
});

const tracePool = computed(() => {
  const traces = props.frame?.llm_decision_traces ?? [];
  return props.focusedAgentId ? traces.filter((trace) => trace.agent_id === props.focusedAgentId) : traces;
});

const traceSummary = computed(() => {
  const traces = tracePool.value;
  const latencies = traces
    .map((trace) => trace.latency_ms)
    .filter((value): value is number => typeof value === "number");
  const totalTokens = traces.reduce((sum, trace) => sum + (trace.total_tokens ?? 0), 0);
  return {
    count: traces.length,
    avgLatency: latencies.length ? latencies.reduce((sum, value) => sum + value, 0) / latencies.length : null,
    totalTokens,
    fallbacks: traces.filter((trace) => !trace.ok || trace.fallback_reason).length,
  };
});

const emptyTraceText = computed(() => {
  if (props.focusedAgentId) return "LLM 模式已开启，但选中单位在当前帧没有记录到 LLM 决策。";
  return "LLM 模式已开启，但当前帧还没有记录到智能体决策。";
});

function teamLabel(team: TeamKey) {
  return team === "red" ? "红方" : "蓝方";
}

function roleLabel(role: RoleKey) {
  const labels: Record<RoleKey, string> = {
    coordinator: "协同",
    scout: "侦察",
    attacker: "攻击",
    defender: "防御",
    support: "支援",
    jammer: "干扰",
    controller: "控制",
    assaulter: "突击",
  };
  return labels[role] ?? role;
}

function actionLabel(value: LlmDecisionTrace["decision_action_type"]) {
  const labels: Record<string, string> = {
    move: "移动",
    attack: "攻击",
    guard: "守卫",
    scout: "侦察",
    support: "支援",
    skill: "技能",
    hold: "待机",
    communicate: "通信",
  };
  return value ? labels[value] ?? value : "未知动作";
}

function fallbackLabel(reason: string | null | undefined) {
  if (!reason) return "无";
  const labels: Record<string, string> = {
    llm_call_failed: "LLM 调用失败，已回退到规则动作",
    timeout: "LLM 请求超时，已回退到规则动作",
    move_target_out_of_bounds: "移动目标越界，已回退到规则动作",
  };
  if (reason.startsWith("invalid_json")) return `模型输出不是有效 JSON（${reason}）`;
  if (reason.startsWith("invalid_action_type")) return `模型动作类型无效（${reason}）`;
  if (reason.startsWith("invalid_target")) return `模型目标无效（${reason}）`;
  return labels[reason] ?? reason;
}

function formatLatency(value: number | null | undefined) {
  return typeof value === "number" ? `${Math.round(value)}ms` : "-";
}

function formatTokens(value: number | null | undefined) {
  return typeof value === "number" ? String(value) : "-";
}
</script>
