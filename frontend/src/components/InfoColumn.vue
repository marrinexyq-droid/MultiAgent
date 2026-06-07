<template>
  <div class="info-column decision-column">
    <section class="section-card focus-unit-card" v-if="frame">
      <div class="section-head compact-head">
        <div><div class="eyebrow">Decision Panel</div><h2>焦点单位</h2></div>
        <div class="phase-chip ghost">{{ focusedLabel }}</div>
      </div>

      <div v-if="focusedUnit" class="focus-unit-body">
        <div class="focus-unit-head">
          <div>
            <div class="focus-unit-id">{{ focusedUnit.agent_id }}</div>
            <p>{{ teamLabel(focusedUnit.team) }} · {{ focusedUnit.role_label }} · {{ focusStateLabel }}</p>
          </div>
          <div class="focus-unit-tag" :class="`team-${focusedUnit.team}`">
            {{ focusStateLabel }}
          </div>
        </div>

        <div class="focus-panel-tabs">
          <button type="button" class="focus-panel-tab-btn" :class="{ active: activeFocusTab === 'actions' }" @click="activeFocusTab = 'actions'">动作</button>
          <button type="button" class="focus-panel-tab-btn" :class="{ active: activeFocusTab === 'risk' }" @click="activeFocusTab = 'risk'">风险</button>
          <button type="button" class="focus-panel-tab-btn" :class="{ active: activeFocusTab === 'judgement' }" @click="activeFocusTab = 'judgement'">判断</button>
        </div>

        <div v-if="activeFocusTab === 'actions'" class="stack-card tactical-card">
          <div class="stack-title">可行动作</div>
          <div class="tactical-pill-row">
            <span v-for="item in focusActions" :key="item" class="tactical-pill actionable">{{ item }}</span>
          </div>
        </div>

        <div v-else-if="activeFocusTab === 'risk'" class="stack-card tactical-card">
          <div class="stack-title">风险提示</div>
          <div class="tactical-note-list">
            <p v-for="item in focusRisks" :key="item">{{ item }}</p>
          </div>
        </div>

        <div v-else class="stack-card tactical-card recommendation-card">
          <div class="stack-title">推荐判断</div>
          <div class="tactical-note-list">
            <p>{{ recommendedJudgement }}</p>
          </div>
        </div>

        <div class="focus-metric-grid compact auxiliary-metrics">
          <div class="mini-metric"><span>HP</span><strong>{{ focusedUnit.hp }}/{{ focusedUnit.max_hp }}</strong></div>
          <div class="mini-metric"><span>资源</span><strong>{{ focusedUnit.ammo }}/{{ focusedUnit.max_ammo }}</strong></div>
          <div class="mini-metric"><span>移动力</span><strong>{{ focusedUnit.movement_points || focusedUnit.move_speed }}</strong></div>
          <div class="mini-metric"><span>射程</span><strong>{{ focusAttackRange }}</strong></div>
          <div class="mini-metric"><span>技能</span><strong>{{ focusedUnit.skill_name }}</strong></div>
          <div class="mini-metric"><span>冷却</span><strong>{{ focusedUnit.skill_cooldown_remaining }}</strong></div>
        </div>
      </div>

      <div v-else class="empty-state compact">点击主舞台中的单位后，这里会切换为决策面板并给出动作、风险和推荐判断。</div>
    </section>

    <LlmDecisionTracePanel
      v-if="frame"
      :frame="frame"
      :focused-agent-id="focusedUnit?.agent_id"
      :limit="focusedUnit ? 1 : 4"
    />

    <section class="section-card right-panel-card" v-if="frame">
      <div class="section-head compact-head">
        <div><div class="eyebrow">Skill Effects</div><h2 class="rail-title">技能影响</h2></div>
      </div>
      <div v-if="effectDetails.length" class="list-stack compact">
        <div v-for="effect in effectDetails" :key="`${effect.effect_type}-${effect.source_id}-${effect.skill_name}`" class="stack-card compact-effect-card">
          <div class="stack-title">{{ effect.skill_name }}</div>
          <p>{{ effect.impact_summary }}</p>
          <small>来源 {{ effect.source_id ?? "-" }} · 影响 {{ effectTargetText(effect) }} · 剩余 {{ effect.duration_remaining }} 回合</small>
        </div>
      </div>
      <div v-else class="empty-state compact">暂无持续技能影响</div>
    </section>

    <section class="section-card right-panel-card" v-if="frame">
      <div class="section-head compact-head">
        <div><div class="eyebrow">Field Intel</div><h2 class="rail-title">态势摘要</h2></div>
      </div>

      <div class="theatre-summary-grid decision-summary-grid">
        <div class="stack-card compact-summary-card" :class="`intel-${teamSummary.red.team}`">
          <div class="stack-title">红方态势</div>
          <p>主威胁 {{ teamSummary.red.threat }} / 活跃任务 {{ teamSummary.red.tasks }}</p>
        </div>
        <div class="stack-card compact-summary-card" :class="`intel-${teamSummary.blue.team}`">
          <div class="stack-title">蓝方态势</div>
          <p>主威胁 {{ teamSummary.blue.threat }} / 活跃任务 {{ teamSummary.blue.tasks }}</p>
        </div>
      </div>

      <div v-if="frame.advice_items?.length" class="stack-card advice-card compact-summary-card">
        <div class="stack-title">系统建议</div>
        <p>{{ frame.advice_items[0]?.rendered_text }}</p>
        <small>{{ frame.advice_items[0]?.evidence_text }}</small>
      </div>

      <div class="memory-tab-row decision-intel-tabs">
        <button type="button" class="memory-tab-btn" :class="{ active: activeIntelTab === 'red' }" @click="activeIntelTab = 'red'">红队详情</button>
        <button type="button" class="memory-tab-btn" :class="{ active: activeIntelTab === 'blue' }" @click="activeIntelTab = 'blue'">蓝队详情</button>
      </div>

      <div class="decision-intel-panel" :class="`team-${activeIntelTab}`">
        <div class="decision-intel-summary">
          <span>主威胁 {{ activeIntel.summary?.primary_threat ?? "无" }}</span>
          <span>任务 {{ activeIntel.tasks.length }}</span>
          <span>风险 {{ activeIntel.risk_zones.length }}</span>
          <span>观测 {{ activeIntel.observations.length }}</span>
        </div>

        <details class="intel-disclosure compact">
          <summary>任务 / 风险 / 观测</summary>
          <div class="decision-intel-stack">
            <div class="decision-intel-block">
              <div class="memory-section-title">任务流</div>
              <p v-if="activeIntel.tasks.length">{{ activeIntel.tasks[0]?.task ?? activeIntel.tasks[0]?.task_id ?? "未命名任务" }} / {{ activeIntel.tasks[0]?.status ?? "pending" }}</p>
              <p v-else>暂无任务流</p>
            </div>
            <div class="decision-intel-block">
              <div class="memory-section-title">风险区</div>
              <p v-if="activeIntel.risk_zones.length">{{ activeIntel.risk_zones[0]?.zone_key ?? "风险区" }} / {{ activeIntel.risk_zones[0]?.reason ?? "未标注" }}</p>
              <p v-else>暂无风险区</p>
            </div>
            <div class="decision-intel-block">
              <div class="memory-section-title">最近观测</div>
              <p v-if="activeIntel.observations.length">{{ activeIntel.observations[0]?.obs_type ?? "观测" }} / {{ activeIntel.observations[0]?.target_id ?? "未知目标" }}</p>
              <p v-else>暂无观测</p>
            </div>
          </div>
        </details>
      </div>

      <div v-if="battleStore.error" class="error-note">{{ battleStore.error }}</div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import LlmDecisionTracePanel from "./LlmDecisionTracePanel.vue";
import { useBattleStore } from "../stores/battle";
import type { BattleFrame, TeamKey } from "../types";

const battleStore = useBattleStore();
const props = defineProps<{ frame: BattleFrame | null }>();
const focusedUnit = computed(() => battleStore.focusedUnit);
const focusedLabel = computed(() => focusedUnit.value?.agent_id ?? "NO FOCUS");
const activeFocusTab = ref<"actions" | "risk" | "judgement">("judgement");
const activeIntelTab = ref<TeamKey>("red");
const effectDetails = computed(() => {
  const effects = props.frame?.effect_details ?? [];
  if (!focusedUnit.value) return effects.slice(0, 2);
  return effects
    .slice()
    .sort((left, right) => Number(effectTouchesFocus(right)) - Number(effectTouchesFocus(left)))
    .slice(0, 2);
});
const teamSummary = computed(() => ({
  red: {
    team: "red",
    threat: props.frame?.memory.red.summary?.primary_threat ?? "无",
    tasks: props.frame?.memory.red.summary?.active_tasks ?? 0,
  },
  blue: {
    team: "blue",
    threat: props.frame?.memory.blue.summary?.primary_threat ?? "无",
    tasks: props.frame?.memory.blue.summary?.active_tasks ?? 0,
  },
}));
const activeIntel = computed(() => props.frame?.memory[activeIntelTab.value] ?? {
  summary: {},
  beliefs: [],
  tasks: [],
  risk_zones: [],
  jammed_zones: [],
  control_blocks: [],
  support_links: [],
  engage_targets: [],
  observations: [],
});

const focusStateLabel = computed(() => {
  if (!focusedUnit.value) return "IDLE";
  if (focusedUnit.value.status_flags.includes("jammed")) return "JAMMED";
  if (focusedUnit.value.status_flags.includes("blocked")) return "PRESSURED";
  if (focusedUnit.value.status_flags.includes("guarded")) return "STABLE";
  return focusedUnit.value.status_flags[0]?.toUpperCase() ?? "STABLE";
});
const focusAttackRange = computed(() => {
  const unit = focusedUnit.value;
  if (!unit) return "-";
  const ranges: Record<string, number> = {
    coordinator: 1,
    scout: 1,
    attacker: 2,
    defender: 1,
    support: 1,
    jammer: 1,
    controller: 1,
    assaulter: 1,
  };
  return ranges[unit.role] ?? 1;
});

const focusActions = computed(() => {
  if (!focusedUnit.value) return [];
  const unit = focusedUnit.value;
  const actions = new Set<string>();
  if (unit.move_speed > 0) actions.add("移动");
  if (unit.skill_cooldown_remaining === 0) actions.add(unit.skill_name);
  if (unit.ammo > 0 && ["attacker", "assaulter", "defender"].includes(unit.role)) actions.add("交战");
  if (unit.role === "defender") actions.add("守卫");
  if (unit.role === "coordinator") actions.add("协同");
  if (unit.role === "support") actions.add("支援");
  if (unit.role === "controller") actions.add("控场");
  if (unit.role === "scout") actions.add("侦察");
  if (unit.role === "jammer") actions.add("干扰");
  return Array.from(actions).slice(0, 4);
});

const focusRisks = computed(() => {
  if (!focusedUnit.value || !props.frame) return [];
  const unit = focusedUnit.value;
  const enemyTeam = unit.team === "red" ? "blue" : "red";
  const nearbyEnemies = props.frame.units.filter((other) => other.team === enemyTeam && other.alive)
    .filter((other) => Math.abs(other.pos.x - unit.pos.x) + Math.abs(other.pos.y - unit.pos.y) <= 2);
  const risks: string[] = [];

  if (nearbyEnemies.length) {
    risks.push(`周边 2 格内存在 ${nearbyEnemies.length} 个敌方单位，最近目标为 ${nearbyEnemies[0].agent_id}。`);
  }
  if (props.frame.memory[enemyTeam].summary?.primary_threat === unit.agent_id) {
    risks.push(`当前已被 ${teamLabel(enemyTeam)}标记为主威胁。`);
  }
  if (unit.skill_cooldown_remaining > 0) {
    risks.push(`技能冷却剩余 ${unit.skill_cooldown_remaining} 回合，爆发动作需要延后。`);
  }
  if (unit.status_flags.includes("jammed")) {
    risks.push("当前受到干扰，协同与判断质量会下降。");
  }
  if (unit.ammo <= Math.max(1, Math.floor(unit.max_ammo / 3))) {
    risks.push("资源接近低位，建议保留关键动作或先补位。");
  }

  return risks.length ? risks.slice(0, 3) : ["周边暂无高压威胁，资源状态允许继续前压或协同。"];
});

const recommendedJudgement = computed(() => {
  if (!focusedUnit.value || !props.frame) return "等待焦点单位后，系统会在这里给出推荐判断。";
  const unit = focusedUnit.value;
  const latestAdvice = props.frame.advice_items.find((item) => item.target_team === unit.team && item.target_role === unit.role);
  if (latestAdvice) return latestAdvice.rendered_text;
  if (unit.role === "defender") return "优先保持护卫位；若敌方前压进入近距，可利用阻挡和守卫稳住中线。";
  if (unit.role === "controller") return "建议维持控场覆盖，先卡关键格，再为前压单位制造安全窗口。";
  if (unit.role === "support") return "建议靠后维持支援链路，优先补足前线单位的持续作战能力。";
  if (unit.role === "scout") return "建议利用机动继续贴近中线侦察，但避免单独深入敌侧控制区。";
  if (unit.role === "attacker" || unit.role === "assaulter") return "优先寻找局部人数优势后再前压，避免在冷却和资源不完整时单点换血。";
  return "建议结合当前控场与附近友军位置推进，优先保持站位完整，再寻找交战窗口。";
});

const tacticalBroadcast = computed(() => {
  if (!props.frame) return "等待战局载入。";
  const redAlive = props.frame.units.filter((unit) => unit.team === "red" && unit.alive).length;
  const blueAlive = props.frame.units.filter((unit) => unit.team === "blue" && unit.alive).length;
  const latestEvent = props.frame.events_structured?.[props.frame.events_structured.length - 1];
  if (focusedUnit.value) return `${focusedUnit.value.agent_id} 为当前焦点。红队 ${redAlive} 单位，蓝队 ${blueAlive} 单位；当前阶段 ${props.frame.phase}。`;
  if (latestEvent) return `${latestEvent.summary} 红队 ${redAlive} 单位，蓝队 ${blueAlive} 单位；当前阶段 ${props.frame.phase}。`;
  return `对抗演练开始。红队 ${redAlive} 单位，蓝队 ${blueAlive} 单位；当前阶段 ${props.frame.phase}。`;
});

function teamLabel(team: TeamKey) {
  return team === "red" ? "RED" : "BLUE";
}

function effectTouchesFocus(effect: BattleFrame["effect_details"][number]) {
  const agentId = focusedUnit.value?.agent_id;
  if (!agentId) return false;
  return effect.source_id === agentId || effect.target_ids.includes(agentId);
}

function effectTargetText(effect: BattleFrame["effect_details"][number]) {
  if (effect.target_ids.length) return effect.target_ids.slice(0, 2).join(" / ");
  if (effect.target_positions.length) {
    const pos = effect.target_positions[0];
    return `(${pos.x}, ${pos.y})`;
  }
  return "区域";
}
</script>
