<template>
  <section class="section-card">
    <div v-if="frame" class="intel-detail-grid">
      <div class="memory-panel team-red">
        <div class="panel-head-strong">
          <div>
            <div class="eyebrow">RED PANEL</div>
            <div class="memory-panel-title">红队详细情报</div>
          </div>
          <div class="phase-chip ghost">{{ focusText(frame.memory.red.summary) }}</div>
        </div>
        <div class="memory-summary">{{ stringifySummary(frame.memory.red.summary) }}</div>
        <div class="memory-stat-row panel-summary-row">
          <div class="meta-card compact-meta">
            <span>主威胁</span>
            <strong>{{ frame.memory.red.summary?.primary_threat ?? "-" }}</strong>
          </div>
          <div class="meta-card compact-meta">
            <span>活跃任务</span>
            <strong>{{ frame.memory.red.summary?.active_tasks ?? 0 }}</strong>
          </div>
          <div class="meta-card compact-meta">
            <span>记忆状态</span>
            <strong>{{ frame.memory.red.summary?.memory_health ?? "-" }}</strong>
          </div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">态势判断</div>
          <div v-if="frame.memory.red.beliefs.length" class="list-stack compact">
            <div v-for="(belief, index) in frame.memory.red.beliefs.slice(0, 4)" :key="`rb-${index}`" class="stack-card">
              <div class="stack-title">{{ belief.target_id ?? "未知目标" }}</div>
              <p>位置 ({{ belief.last_known_position?.x ?? "-" }}, {{ belief.last_known_position?.y ?? "-" }}) / 趋势 {{ belief.trend ?? "uncertain" }} / 威胁 {{ belief.threat_level ?? "low" }}</p>
              <small>置信 {{ formatFloat(belief.confidence_score) }} · T{{ belief.last_seen_turn ?? "-" }}</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无判断</div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">任务流</div>
          <div v-if="frame.memory.red.tasks.length" class="list-stack compact">
            <div v-for="(task, index) in frame.memory.red.tasks.slice(0, 4)" :key="`rt-${index}`" class="stack-card">
              <div class="stack-title">{{ task.task ?? task.task_id ?? "未命名任务" }}</div>
              <p>状态 {{ task.status ?? "pending" }} / 执行者 {{ task.assignee ?? "-" }} / 目标 {{ task.target_id ?? "-" }}</p>
              <small>置信 {{ formatFloat(task.confidence) }} · T{{ task.updated_turn ?? "-" }}</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无任务</div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">最近观测</div>
          <div v-if="frame.memory.red.observations.length" class="list-stack compact">
            <div v-for="(obs, index) in frame.memory.red.observations.slice(0, 3)" :key="`ro-${index}`" class="stack-card">
              <div class="stack-title">{{ obs.target_id ?? obs.obs_type ?? "观测" }}</div>
              <p>类型 {{ obs.obs_type ?? "unknown" }} / 位置 ({{ obs.position?.x ?? "-" }}, {{ obs.position?.y ?? "-" }}) / 上报者 {{ obs.source_agent_id ?? "-" }}</p>
              <small>置信 {{ formatFloat(obs.confidence) }} · T{{ obs.timestamp ?? "-" }}</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无观测</div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">风险区</div>
          <div v-if="frame.memory.red.risk_zones.length" class="list-stack compact">
            <div v-for="(risk, index) in frame.memory.red.risk_zones.slice(0, 3)" :key="`rr-${index}`" class="stack-card">
              <div class="stack-title">风险区 {{ risk.zone_key ?? "-" }}</div>
              <p>原因 {{ risk.reason ?? "未标注" }} / 上报者 {{ risk.reporter ?? "-" }}</p>
              <small>置信 {{ formatFloat(risk.confidence) }} · T{{ risk.timestamp ?? "-" }}</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无风险区</div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">干扰 / 封锁</div>
          <div v-if="frame.memory.red.jammed_zones.length || frame.memory.red.control_blocks.length" class="list-stack compact">
            <div v-for="(zone, index) in frame.memory.red.jammed_zones.slice(0, 2)" :key="`rj-${index}`" class="stack-card">
              <div class="stack-title">干扰区</div>
              <p>中心 ({{ zone.center?.x ?? "-" }}, {{ zone.center?.y ?? "-" }}) / 来源 {{ zone.source_id ?? "-" }}</p>
              <small>持续 {{ zone.turns_remaining ?? "-" }} 回合</small>
            </div>
            <div v-for="(zone, index) in frame.memory.red.control_blocks.slice(0, 2)" :key="`rc-${index}`" class="stack-card">
              <div class="stack-title">封锁区</div>
              <p>中心 ({{ zone.center?.x ?? "-" }}, {{ zone.center?.y ?? "-" }}) / 阵营 {{ zone.team ?? "-" }}</p>
              <small>持续 {{ zone.turns_remaining ?? "-" }} 回合</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无干扰与封锁</div>
        </div>
      </div>

      <div class="memory-panel team-blue">
        <div class="panel-head-strong">
          <div>
            <div class="eyebrow">BLUE PANEL</div>
            <div class="memory-panel-title">蓝队详细情报</div>
          </div>
          <div class="phase-chip ghost">{{ focusText(frame.memory.blue.summary) }}</div>
        </div>
        <div class="memory-summary">{{ stringifySummary(frame.memory.blue.summary) }}</div>
        <div class="memory-stat-row panel-summary-row">
          <div class="meta-card compact-meta">
            <span>主威胁</span>
            <strong>{{ frame.memory.blue.summary?.primary_threat ?? "-" }}</strong>
          </div>
          <div class="meta-card compact-meta">
            <span>活跃任务</span>
            <strong>{{ frame.memory.blue.summary?.active_tasks ?? 0 }}</strong>
          </div>
          <div class="meta-card compact-meta">
            <span>记忆状态</span>
            <strong>{{ frame.memory.blue.summary?.memory_health ?? "-" }}</strong>
          </div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">态势判断</div>
          <div v-if="frame.memory.blue.beliefs.length" class="list-stack compact">
            <div v-for="(belief, index) in frame.memory.blue.beliefs.slice(0, 4)" :key="`bb-${index}`" class="stack-card">
              <div class="stack-title">{{ belief.target_id ?? "未知目标" }}</div>
              <p>位置 ({{ belief.last_known_position?.x ?? "-" }}, {{ belief.last_known_position?.y ?? "-" }}) / 趋势 {{ belief.trend ?? "uncertain" }} / 威胁 {{ belief.threat_level ?? "low" }}</p>
              <small>置信 {{ formatFloat(belief.confidence_score) }} · T{{ belief.last_seen_turn ?? "-" }}</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无判断</div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">任务流</div>
          <div v-if="frame.memory.blue.tasks.length" class="list-stack compact">
            <div v-for="(task, index) in frame.memory.blue.tasks.slice(0, 4)" :key="`bt-${index}`" class="stack-card">
              <div class="stack-title">{{ task.task ?? task.task_id ?? "未命名任务" }}</div>
              <p>状态 {{ task.status ?? "pending" }} / 执行者 {{ task.assignee ?? "-" }} / 目标 {{ task.target_id ?? "-" }}</p>
              <small>置信 {{ formatFloat(task.confidence) }} · T{{ task.updated_turn ?? "-" }}</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无任务</div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">最近观测</div>
          <div v-if="frame.memory.blue.observations.length" class="list-stack compact">
            <div v-for="(obs, index) in frame.memory.blue.observations.slice(0, 3)" :key="`bo-${index}`" class="stack-card">
              <div class="stack-title">{{ obs.target_id ?? obs.obs_type ?? "观测" }}</div>
              <p>类型 {{ obs.obs_type ?? "unknown" }} / 位置 ({{ obs.position?.x ?? "-" }}, {{ obs.position?.y ?? "-" }}) / 上报者 {{ obs.source_agent_id ?? "-" }}</p>
              <small>置信 {{ formatFloat(obs.confidence) }} · T{{ obs.timestamp ?? "-" }}</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无观测</div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">风险区</div>
          <div v-if="frame.memory.blue.risk_zones.length" class="list-stack compact">
            <div v-for="(risk, index) in frame.memory.blue.risk_zones.slice(0, 3)" :key="`br-${index}`" class="stack-card">
              <div class="stack-title">风险区 {{ risk.zone_key ?? "-" }}</div>
              <p>原因 {{ risk.reason ?? "未标注" }} / 上报者 {{ risk.reporter ?? "-" }}</p>
              <small>置信 {{ formatFloat(risk.confidence) }} · T{{ risk.timestamp ?? "-" }}</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无风险区</div>
        </div>
        <div class="memory-section">
          <div class="memory-section-title">干扰 / 封锁</div>
          <div v-if="frame.memory.blue.jammed_zones.length || frame.memory.blue.control_blocks.length" class="list-stack compact">
            <div v-for="(zone, index) in frame.memory.blue.jammed_zones.slice(0, 2)" :key="`bj-${index}`" class="stack-card">
              <div class="stack-title">干扰区</div>
              <p>中心 ({{ zone.center?.x ?? "-" }}, {{ zone.center?.y ?? "-" }}) / 来源 {{ zone.source_id ?? "-" }}</p>
              <small>持续 {{ zone.turns_remaining ?? "-" }} 回合</small>
            </div>
            <div v-for="(zone, index) in frame.memory.blue.control_blocks.slice(0, 2)" :key="`bc-${index}`" class="stack-card">
              <div class="stack-title">封锁区</div>
              <p>中心 ({{ zone.center?.x ?? "-" }}, {{ zone.center?.y ?? "-" }}) / 阵营 {{ zone.team ?? "-" }}</p>
              <small>持续 {{ zone.turns_remaining ?? "-" }} 回合</small>
            </div>
          </div>
          <div v-else class="empty-state compact">暂无干扰与封锁</div>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">暂无详细情报</div>
  </section>
</template>

<script setup lang="ts">
import type { BattleFrame } from "../types";
import { useBattleStore } from "../stores/battle";

defineProps<{ frame: BattleFrame | null }>();
const battleStore = useBattleStore();

function stringifySummary(summary: Record<string, unknown> | undefined) {
  if (!summary) return "暂无情报";
  return `主威胁 ${summary.primary_threat ?? "无"} / 活跃任务 ${summary.active_tasks ?? 0} / 建议 ${summary.recommended_focus ?? "无"} / 记忆状态 ${summary.memory_health ?? "unknown"}`;
}

function focusText(summary: Record<string, unknown> | undefined) {
  const focused = battleStore.focusedUnit?.agent_id;
  if (focused) return `focus / ${focused}`;
  if (!summary) return "focus / none";
  return `focus / ${summary.primary_threat ?? "none"}`;
}

function formatFloat(value: unknown) {
  if (typeof value !== "number") return "-";
  return value.toFixed(2);
}
</script>
