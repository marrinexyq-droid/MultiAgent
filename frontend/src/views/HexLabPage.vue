<template>
  <main class="hex-lab-page">
    <section class="hex-lab-topbar">
      <div>
        <div class="eyebrow">Experimental Mode</div>
        <h1>六边形试验场</h1>
        <p>独立测试 hex 拓扑：6 邻接移动、hex 距离、hex 范围与专属沙盘渲染。</p>
      </div>
      <div class="hex-lab-actions">
        <label class="hex-preset-select">
          地形预设
          <select v-model="terrainPreset">
            <option value="plains">开阔平原</option>
            <option value="jungle">丛林地带</option>
            <option value="urban">城市战区</option>
          </select>
        </label>
        <div class="hex-view-toggle" role="tablist" aria-label="视角切换">
          <button role="tab" :aria-selected="viewTeam === 'all'" :class="{ active: viewTeam === 'all' }" @click="viewTeam = 'all'">全面视角</button>
          <button role="tab" :aria-selected="viewTeam === 'red'" :class="{ active: viewTeam === 'red' }" @click="viewTeam = 'red'">🔴 红方</button>
          <button role="tab" :aria-selected="viewTeam === 'blue'" :class="{ active: viewTeam === 'blue' }" @click="viewTeam = 'blue'">🔵 蓝方</button>
        </div>
        <button
          type="button"
          class="hex-diff-toggle"
          :class="{ active: showDiffs }"
          @click="showDiffs = !showDiffs"
          :title="showDiffs ? '隐藏帧对比' : '显示帧对比'"
        >对比</button>
        <button
          type="button"
          class="hex-diff-toggle"
          :class="{ active: showInfluence }"
          @click="showInfluence = !showInfluence"
          :title="showInfluence ? '隐藏影响力' : '显示影响力'"
        >影响</button>
        <RouterLink class="secondary-btn" to="/deployment">返回部署</RouterLink>
        <button type="button" class="primary-btn" :disabled="loading" @click="createAndRunHexBattle">
          {{ battleId ? "重新创建 Hex 演练" : "创建 Hex 演练" }}
        </button>
      </div>
    </section>

    <section class="hex-lab-console">
      <div class="hex-lab-main">
        <HexBattleMap :frame="currentFrame" :focused-agent-id="focusedAgentId" :selected-team="viewTeam" :previous-frame="previousFrame" :show-diffs="showDiffs" :show-influence="showInfluence" :focused-unit-info="focusedUnitInfo" :timeline-markers="timelineBarData" @focus-agent="focusedAgentId = $event" @jump="jumpToMarker" />
        <HexControlBar
          :current-index="currentIndex"
          :max-index="maxIndex"
          :playing="playing"
          :playback-speed="playbackSpeed"
          @start="seek(0)"
          @prev="seek(Math.max(0, currentIndex - 1))"
          @toggle="togglePlayback"
          @next="seek(Math.min(maxIndex, currentIndex + 1))"
          @latest="seek(maxIndex)"
          @seek="seek"
          @speed="playbackSpeed = $event"
        />
      </div>

      <aside class="hex-lab-side hex-side-scroll">
        <div class="hex-side-card hex-side-compact">
          <div class="hex-side-compact-row">
            <div>
              <div class="eyebrow">{{ battleId || "等待创建" }}</div>
              <div class="hex-compact-status"><span :class="`status-${status}`"></span>{{ status === "running" ? "推演中" : status === "done" ? "已完成" : "待命" }}</div>
            </div>
            <div class="hex-compact-round">T{{ currentFrame?.turn ?? 0 }}</div>
          </div>
          <div class="hex-dashboard" v-if="currentFrame">
            <div class="hex-dash-team">
              <span class="hex-dash-label">🔴</span>
              <span class="hex-dash-bar"><span class="hex-dash-fill dash-red" :style="{ width: dashRedPct + '%' }"></span></span>
              <span class="hex-dash-stat">{{ dashRedAlive }}/{{ dashRedTotal }}</span>
              <span class="hex-dash-label">🔵</span>
              <span class="hex-dash-bar"><span class="hex-dash-fill dash-blue" :style="{ width: dashBluePct + '%' }"></span></span>
              <span class="hex-dash-stat">{{ dashBlueAlive }}/{{ dashBlueTotal }}</span>
              <span class="hex-dash-stat muted">均HP {{ dashAvgHp }}</span>
            </div>
          </div>
          <div class="hex-ring-row" v-if="currentFrame">
            <HexRingGauge :value="ringFuel" label="FUEL" color="#00d4ff" />
            <HexRingGauge :value="ringAmmo" label="AMMO" :color="ringAmmoColor" />
            <HexRingGauge :value="ringHealth" label="HEALTH" :color="ringHealthColor" />
            <HexRingGauge :value="ringAtk" label="FIREPWR" :color="ringAtkColor" />
          </div>
        </div>

        <div class="hex-side-card hex-side-tabs-card" v-if="currentFrame">
          <div class="hex-side-tab-row">
            <button :class="{ active: sideTab === 'unit' }" @click="sideTab = 'unit'" :disabled="!focusedUnit">单位</button>
            <button :class="{ active: sideTab === 'decision' }" @click="sideTab = 'decision'" :disabled="!focusedUnit">决策</button>
            <button :class="{ active: sideTab === 'combat' }" @click="sideTab = 'combat'" :disabled="!combatInfo">战斗</button>
            <button :class="{ active: sideTab === 'legend' }" @click="sideTab = 'legend'">图例</button>
          </div>
          <div class="hex-side-tab-body">
            <!-- Tab: Unit (info card style) -->
            <template v-if="sideTab === 'unit'">
              <template v-if="focusedUnit">
                <div class="hex-unit-card" :class="`card-${focusedUnit.team}`" :style="{ '--role-color': roleColor }">
                  <div class="unit-card-head">
                    <div class="unit-card-icon-wrap" :style="{ borderColor: roleColor }">
                      <span class="unit-card-icon">{{ roleIcon }}</span>
                    </div>
                    <div>
                      <span class="unit-card-role">{{ focusedUnit.role_label }}</span>
                      <span class="unit-card-desc">{{ roleDesc }}</span>
                      <span class="unit-card-id">{{ focusedUnit.agent_id }}</span>
                    </div>
                    <div style="text-align:right">
                      <span class="unit-card-badge" :class="`team-${focusedUnit.team}`">{{ focusedUnit.team === "red" ? "敌方" : "己方" }}</span>
                      <div class="unit-card-score">{{ scoreAvg }}<small>/100</small></div>
                    </div>
                  </div>
                  <div class="unit-card-attrs">
                    <div class="unit-attr-row"><span class="attr-label">{{ roleStatLabel }}</span><div class="attr-track"><div class="attr-fill" :style="{ width: attrStatPct + '%', background: roleColor }"></div></div><span class="attr-val">{{ attrStatPct }}%</span><span class="attr-dot" :style="{ background: roleColor }"></span></div>
                    <div class="unit-attr-row"><span class="attr-label">HP</span><div class="attr-track"><div class="attr-fill" :style="{ width: attrHpPct + '%', background: attrHpColor }"></div></div><span class="attr-val">{{ attrHpPct }}%</span><span class="attr-dot" :style="{ background: attrHpColor }"></span></div>
                    <div class="unit-attr-row"><span class="attr-label">ATK</span><div class="attr-track"><div class="attr-fill" :style="{ width: attrAtkPct + '%', background: attrAtkColor }"></div></div><span class="attr-val">{{ attrAtkPct }}%</span><span class="attr-dot" :style="{ background: attrAtkColor }"></span></div>
                    <div class="unit-attr-row"><span class="attr-label">AMMO</span><div class="attr-track"><div class="attr-fill" :style="{ width: attrAmmoPct + '%', background: attrAmmoColor }"></div></div><span class="attr-val">{{ attrAmmoPct }}%</span><span class="attr-dot" :style="{ background: attrAmmoColor }"></span></div>
                    <div class="unit-attr-row"><span class="attr-label">MOB</span><div class="attr-track"><div class="attr-fill" :style="{ width: attrMobPct + '%', background: attrMobColor }"></div></div><span class="attr-val">{{ attrMobPct }}%</span><span class="attr-dot" :style="{ background: attrMobColor }"></span></div>
                  </div>
                  <div class="unit-card-footer">
                    <span>{{ focusedUnit.skill_name }}</span>
                    <span :class="`status-${statusTag}`">{{ statusText }}</span>
                  </div>
                </div>
              </template>
              <p v-else class="hex-muted">点击单位查看详情</p>
            </template>

            <!-- Tab: Decision -->
            <template v-if="sideTab === 'decision' && focusedUnit && focusedDecision">
              <div class="hex-decision-log" style="margin-top:0">
                <div class="hex-decision-section"><span class="hex-decision-label">最后行动</span><span class="hex-decision-value">{{ focusedDecision.lastAction }}</span></div>
                <div class="hex-decision-section" v-if="focusedDecision.task"><span class="hex-decision-label">当前任务</span><span class="hex-decision-value">{{ focusedDecision.task }}</span></div>
                <div class="hex-decision-section" v-if="focusedDecision.threat"><span class="hex-decision-label">威胁判断</span><span class="hex-decision-value">{{ focusedDecision.threat }}</span></div>
                <div class="hex-decision-section" v-if="focusedDecision.terrainNote"><span class="hex-decision-label">地形评估</span><span class="hex-decision-value">{{ focusedDecision.terrainNote }}</span></div>
              </div>
            </template>

            <!-- Tab: Combat -->
            <template v-if="sideTab === 'combat' && combatInfo">
              <div class="hex-combat-grid"><div class="hex-combat-side team-red-soft"><div class="hex-combat-label">攻击方</div><div class="hex-combat-id">{{ combatInfo.attacker }}</div><div class="hex-meta-row"><span>攻击力</span><strong>{{ combatInfo.attackPower }}</strong></div></div><div class="hex-combat-vs">⚔</div><div class="hex-combat-side team-blue-soft"><div class="hex-combat-label">防御方</div><div class="hex-combat-id">{{ combatInfo.defender }}</div><div class="hex-meta-row"><span>掩护</span><strong>{{ combatInfo.cover }}</strong></div></div></div>
              <div class="hex-combat-result" v-if="combatInfo.damage">实际伤害: <strong>{{ combatInfo.damage }}</strong> <span v-if="combatInfo.coverPct">(原始{{ combatInfo.rawDamage }}, {{ combatInfo.coverPct }})</span></div>
            </template>

            <!-- Tab: Legend -->
            <template v-if="sideTab === 'legend'">
              <div class="hex-terrain-legend" style="margin-top:0">
                <div v-for="t in terrainTypes" :key="t.key" class="hex-legend-row"><span class="hex-legend-swatch" :class="`swatch-${t.key}`"></span><span class="hex-legend-label">{{ t.label }}</span><span class="hex-legend-cost">{{ t.cost }}MP</span></div>
              </div>
            </template>
          </div>
        </div>
      </aside>
    </section>

    <p v-if="error" class="hex-error" role="alert" aria-live="polite">{{ error }}</p>

    <footer class="hex-footer">CLASSIFIED &#47;&#47; FOR COMMAND USE ONLY  |  HEX LAB v2.4.1  |  ID: CMD-HEX-2024</footer>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { createBattle, fetchRoles, openBattleStream, startBattle } from "../api";
import HexBattleMap from "../components/HexBattleMap.vue";
import HexControlBar from "../components/HexControlBar.vue";
import HexRingGauge from "../components/HexRingGauge.vue";
import type { BattleFrame, RolesResponse, ScenarioConfig, TeamConfigPayload } from "../types";

const roles = ref<RolesResponse | null>(null);
const battleId = ref("");
const frames = ref<BattleFrame[]>([]);
const currentIndex = ref(0);
const loading = ref(false);
const status = ref("idle");
const error = ref("");
const focusedAgentId = ref("");
const source = ref<EventSource | null>(null);
const playing = ref(false);
const playbackSpeed = ref(1);
const terrainPreset = ref("plains");
const viewTeam = ref("all");
const showDiffs = ref(false);
const showInfluence = ref(false);
const sideTab = ref("unit");
let playbackTimer: number | null = null;

const terrainPresetLabel = computed(() => {
  const labels: Record<string, string> = { plains: "开阔平原", jungle: "丛林地带", urban: "城市战区" };
  return labels[terrainPreset.value] ?? terrainPreset.value;
});

const terrainTypes = [
  { key: "open", label: "开阔地", cost: 2, cover: "无" },
  { key: "road", label: "道路", cost: 1, cover: "无" },
  { key: "forest", label: "森林", cost: 4, cover: "25%" },
  { key: "urban", label: "城区", cost: 3, cover: "40%" },
  { key: "water", label: "水域", cost: 5, cover: "无" },
  { key: "rough", label: "崎岖", cost: 5, cover: "15%" },
  { key: "marsh", label: "沼泽", cost: 6, cover: "10%" },
  { key: "mountain", label: "山地", cost: 6, cover: "35%" },
];

const terrainLabelMap: Record<string, string> = {
  open: "开阔", road: "道路", forest: "森林", urban: "城区",
  water: "水域", rough: "崎岖", marsh: "沼泽", mountain: "山地",
};

function terrainCostStr(pos: { x: number; y: number }): string {
  const frame = currentFrame.value;
  if (!frame?.map.terrain) return "";
  if (pos.y < 0 || pos.y >= frame.map.terrain.length) return "";
  const row = frame.map.terrain[pos.y];
  if (!row || pos.x < 0 || pos.x >= row.length) return "";
  const cell = row[pos.x];
  const costs: Record<string, number> = { open: 2, road: 1, forest: 4, urban: 3, water: 5, rough: 5, marsh: 6, mountain: 6 };
  const covers: Record<string, string> = { open: "无", road: "无", forest: "25%", urban: "40%", water: "无", rough: "15%", marsh: "10%", mountain: "35%" };
  const t = cell?.type ?? "open";
  return `成本${costs[t] ?? 2}MP 掩护${covers[t] ?? "无"}`;
}
function terrainCoverStr(pos: { x: number; y: number }): string {
  const frame = currentFrame.value;
  if (!frame?.map.terrain) return "无";
  if (pos.y < 0 || pos.y >= frame.map.terrain.length) return "无";
  const row = frame.map.terrain[pos.y];
  if (!row || pos.x < 0 || pos.x >= row.length) return "无";
  const cell = row[pos.x];
  const covers: Record<string, string> = { open: "无", road: "无", forest: "25%", urban: "40%", water: "无", rough: "15%", marsh: "10%", mountain: "35%" };
  return covers[cell?.type ?? "open"] ?? "无";
}

const focusedDecision = computed(() => {
  const frame = currentFrame.value;
  const unit = focusedUnit.value;
  if (!frame || !unit) return null;
  const lastEvent = frame.events_structured?.slice().reverse().find((e) => e.actor_id === unit.agent_id);
  const team = unit.team;
  const mem = frame.memory?.[team];
  const task = mem?.tasks?.slice().reverse().find((t) => t.assignee === unit.agent_id);
  const belief = mem?.beliefs?.slice().reverse()[0];
  const advice = frame.advice_items?.slice().reverse().find((a) => a.target_role === unit.role && a.target_team === unit.team);
  const terrainNote = `${terrainLabelMap[terrainAtPos(unit.pos)] ?? ""} · ${terrainCostStr(unit.pos)}`;
  const actionLabels: Record<string, string> = {
    move: "移动到目标位置", attack: "攻击目标", skill: "使用技能",
    scout: "侦察周边", communicate: "发送信息", hold: "待命",
  };
  return {
    lastAction: lastEvent ? `${actionLabels[lastEvent.type.toLowerCase()] ?? lastEvent.type} → ${lastEvent.summary?.slice(0, 60) ?? ""}` : "首次部署",
    task: task?.task ?? (mem?.summary?.recommended_focus ?? undefined),
    threat: belief ? `${belief.target_id} (置信度${Math.round((belief.confidence_score ?? 0) * 100)}%)` : undefined,
    terrainNote,
  };
});

const combatInfo = computed(() => {
  const frame = currentFrame.value;
  const unit = focusedUnit.value;
  if (!frame || !unit) return null;
  const attackEvent = frame.events_structured?.slice().reverse().find((e) => (e.actor_id === unit.agent_id || e.target_id === unit.agent_id) && e.type === "ATTACK");
  if (!attackEvent) return null;
  const meta = attackEvent.metadata as Record<string, unknown> || {};
  const isAttacker = attackEvent.actor_id === unit.agent_id;
  const targetId = attackEvent.target_id;
  const target = targetId ? frame.units.find((u) => u.agent_id === targetId) : null;
  return {
    attacker: isAttacker ? unit.agent_id : (attackEvent.actor_id ?? "?"),
    defender: isAttacker ? (targetId ?? "?") : unit.agent_id,
    attackPower: isAttacker ? unit.attack_power : (target?.attack_power ?? 0),
    cover: !isAttacker ? (meta.terrain_cover ? `${Math.round(Number(meta.terrain_cover) * 100)}%` : terrainCoverStr(unit.pos)) : "-",
    coverPct: meta.terrain_cover ? `${Math.round(Number(meta.terrain_cover) * 100)}%` : undefined,
    rawDamage: meta.raw_damage ?? undefined,
    damage: meta.damage ?? undefined,
  };
});

function terrainAtPos(pos: { x: number; y: number }): string {
  const frame = currentFrame.value;
  if (!frame?.map.terrain) return "未知";
  if (pos.y < 0 || pos.y >= frame.map.terrain.length) return "未知";
  const row = frame.map.terrain[pos.y];
  if (!row || pos.x < 0 || pos.x >= row.length) return "未知";
  const cell = row[pos.x];
  return terrainLabelMap[cell?.type ?? ""] ?? "未知";
}

const scenario = computed<ScenarioConfig>(() => {
  const base = terrainPreset.value;
  return {
    width: 10,
    height: 8,
    grid_type: "hex",
    terrain_preset: base,
    red_spawn_zones: [{ x: 0, y: 0, width: 3, height: 8 }],
    blue_spawn_zones: [{ x: 7, y: 0, width: 3, height: 8 }],
    control_zones: [{ x: 4, y: 3, width: 2, height: 2 }],
  };
});

const currentFrame = computed(() => frames.value[currentIndex.value] ?? null);
const previousFrame = computed(() => currentIndex.value > 0 ? frames.value[currentIndex.value - 1] ?? null : null);
const dashRedAlive = computed(() => currentFrame.value?.units.filter((u) => u.team === "red" && u.alive).length ?? 0);
const dashRedTotal = computed(() => currentFrame.value?.units.filter((u) => u.team === "red").length ?? 1);
const dashBlueAlive = computed(() => currentFrame.value?.units.filter((u) => u.team === "blue" && u.alive).length ?? 0);
const dashBlueTotal = computed(() => currentFrame.value?.units.filter((u) => u.team === "blue").length ?? 1);
const dashRedPct = computed(() => (dashRedAlive.value / Math.max(1, dashRedTotal.value)) * 100);
const dashBluePct = computed(() => (dashBlueAlive.value / Math.max(1, dashBlueTotal.value)) * 100);
const dashSurvivalRate = computed(() => {
  const a = dashRedAlive.value + dashBlueAlive.value;
  const t = dashRedTotal.value + dashBlueTotal.value;
  return t > 0 ? `${Math.round((a / t) * 100)}%` : "-";
});
const dashAvgHp = computed(() => {
  const u = currentFrame.value?.units.filter((u2) => u2.alive) ?? [];
  if (!u.length) return "-";
  const avg = Math.round(u.reduce((s, u2) => s + (u2.hp / Math.max(1, u2.max_hp)), 0) / u.length * 100);
  return `${avg}%`;
});
const ringFuel = computed(() => {
  const u = currentFrame.value?.units ?? [];
  if (!u.length) return 0;
  const avg = u.reduce((s, u2) => s + (u2.remaining_mp || u2.move_speed || 6), 0) / u.length;
  return Math.round((avg / 10) * 100);
});
const ringAmmo = computed(() => {
  const u = currentFrame.value?.units ?? [];
  if (!u.length) return 0;
  const avg = u.reduce((s, u2) => s + (u2.ammo / Math.max(1, u2.max_ammo)), 0) / u.length;
  return Math.round(avg * 100);
});
const ringAmmoColor = computed(() => ringAmmo.value > 60 ? "var(--hex-success)" : ringAmmo.value > 30 ? "var(--hex-warning)" : "var(--hex-danger)");
const ringHealth = computed(() => {
  const u = currentFrame.value?.units ?? [];
  if (!u.length) return 0;
  const avg = u.reduce((s, u2) => s + (u2.hp / Math.max(1, u2.max_hp)), 0) / u.length;
  return Math.round(avg * 100);
});
const ringHealthColor = computed(() => ringHealth.value > 60 ? "var(--hex-success)" : ringHealth.value > 30 ? "var(--hex-warning)" : "var(--hex-danger)");
const ringAtk = computed(() => {
  const u = currentFrame.value?.units ?? [];
  if (!u.length) return 0;
  const avg = u.reduce((s, u2) => s + (u2.attack_power / 42), 0) / u.length;
  return Math.round(Math.min(100, avg * 100));
});
const ringAtkColor = computed(() => ringAtk.value > 60 ? "var(--hex-success)" : ringAtk.value > 30 ? "var(--hex-warning)" : "var(--hex-danger)");
const maxIndex = computed(() => Math.max(0, frames.value.length - 1));
const focusedUnit = computed(() => currentFrame.value?.units.find((unit) => unit.agent_id === focusedAgentId.value) ?? null);
const focusedUnitInfo = computed(() => {
  const u = focusedUnit.value;
  if (!u) return null;
  return { vision: u.vision_range, attack: u.attack_range, pos: u.pos };
});
const attrHpPct = computed(() => {
  const u = focusedUnit.value;
  return u && u.max_hp ? Math.round((u.hp / u.max_hp) * 100) : 0;
});
const attrHpColor = computed(() => attrHpPct.value > 60 ? "var(--hex-success)" : attrHpPct.value > 30 ? "var(--hex-warning)" : "var(--hex-danger)");
const attrAtkPct = computed(() => {
  const u = focusedUnit.value;
  return u ? Math.min(100, Math.round((u.attack_power / 42) * 100)) : 0;
});
const attrAtkColor = computed(() => attrAtkPct.value > 60 ? "var(--hex-success)" : attrAtkPct.value > 30 ? "var(--hex-warning)" : "var(--hex-danger)");
const attrAmmoPct = computed(() => {
  const u = focusedUnit.value;
  return u && u.max_ammo ? Math.round((u.ammo / u.max_ammo) * 100) : 0;
});
const attrAmmoColor = computed(() => attrAmmoPct.value > 60 ? "var(--hex-success)" : attrAmmoPct.value > 30 ? "var(--hex-warning)" : "var(--hex-danger)");
const attrMobPct = computed(() => {
  const u = focusedUnit.value;
  const maxMp = Math.max(u?.movement_points ?? 6, 6);
  const curMp = u?.remaining_mp ?? maxMp;
  return Math.round((curMp / maxMp) * 100);
});
const attrMobColor = computed(() => attrMobPct.value > 60 ? "var(--hex-success)" : attrMobPct.value > 30 ? "var(--hex-warning)" : "var(--hex-danger)");
const ROLE_META: Record<string, { icon: string; color: string; desc: string; statKey: string }> = {
  coordinator: { icon: "🎯", color: "#fbbf24", desc: "信息聚合与任务分配", statKey: "vision_range" },
  scout:      { icon: "👁", color: "#3b82f6", desc: "侦察与情报获取", statKey: "vision_range" },
  attacker:   { icon: "⚔", color: "#ef4444", desc: "主力突破单位", statKey: "attack_power" },
  defender:   { icon: "🛡", color: "#22c55e", desc: "阵线稳固核心", statKey: "hp" },
  support:    { icon: "🔧", color: "#06b6d4", desc: "维持续航能力", statKey: "ammo" },
  jammer:     { icon: "📡", color: "#a855f7", desc: "信息战与干扰", statKey: "vision_range" },
  controller: { icon: "🔒", color: "#f97316", desc: "区域封锁控制", statKey: "attack_power" },
  assaulter:  { icon: "💥", color: "#ec4899", desc: "高机动破局单位", statKey: "move_speed" },
};
const roleIcon = computed(() => ROLE_META[focusedUnit.value?.role ?? ""]?.icon ?? "❓");
const roleColor = computed(() => ROLE_META[focusedUnit.value?.role ?? ""]?.color ?? "#666");
const roleDesc = computed(() => ROLE_META[focusedUnit.value?.role ?? ""]?.desc ?? "");
const roleStatLabel = computed(() => {
  const sk = ROLE_META[focusedUnit.value?.role ?? ""]?.statKey ?? "";
  const labels: Record<string, string> = { vision_range: "视野", attack_power: "火力", hp: "耐久", ammo: "弹药", move_speed: "机动" };
  return labels[sk] ?? "核心";
});
const attrStatPct = computed(() => {
  const u = focusedUnit.value;
  if (!u) return 0;
  const sk = ROLE_META[u.role]?.statKey ?? "hp";
  let val = 0;
  if (sk === "vision_range") val = (u.vision_range / 7) * 100;
  else if (sk === "attack_power") val = (u.attack_power / 42) * 100;
  else if (sk === "hp") val = (u.hp / u.max_hp) * 100;
  else if (sk === "ammo") val = (u.ammo / u.max_ammo) * 100;
  else if (sk === "move_speed") val = ((u.movement_points || u.move_speed) / 10) * 100;
  return Math.min(100, Math.round(val));
});
const scoreAvg = computed(() => {
  const values = [attrHpPct.value, attrAtkPct.value, attrAmmoPct.value, attrMobPct.value];
  return Math.round(values.reduce((a, b) => a + b, 0) / values.length);
});
const statusTag = computed(() => {
  if (!focusedUnit.value?.alive) return "dead";
  const f = focusedUnit.value?.status_flags ?? [];
  if (f.includes("jammed")) return "warning";
  if (focusedUnit.value && focusedUnit.value.hp <= focusedUnit.value.max_hp * 0.45) return "critical";
  return "ready";
});

const statusText = computed(() => {
  const u = focusedUnit.value;
  if (!u) return "";
  const flags = u.status_flags ?? [];
  if (!u.alive) return "失效";
  if (flags.includes("jammed")) return "干扰·无法使用技能";
  if (flags.includes("blocked")) return "封锁·无法移动";
  if (u.hp <= u.max_hp * 0.45) return `受损·HP ${u.hp}/${u.max_hp}`;
  if (flags.includes("exposed")) return "暴露·易受攻击";
  return "待命";
});
const recentMarkers = computed(() => frames.value.flatMap((frame) => frame.timeline_markers ?? []).slice(-8).reverse());
const timelineBarData = computed(() => {
  const all = frames.value.flatMap((frame) => frame.timeline_markers ?? []);
  const maxTurn = Math.max(1, frames.value.length - 1);
  return all.map((m) => ({
    ...m,
    pct: (m.turn / maxTurn) * 100,
  }));
});
const MARKER_ICONS: Record<string, string> = {
  START: "▶", RESULT: "🏁", DOWN: "✕", ATTACK: "⚔", MOVE: "➜",
  SPOT: "👁", SKILL: "✦", TASK: "📋", JAM: "📡", BLOCK: "🔒",
  ENGAGE: "💥", SUPPORT: "💚", GUARD: "🛡",
};
function markerIcon(type: string): string {
  return MARKER_ICONS[type.toUpperCase()] ?? "●";
}

watch([playing, playbackSpeed, maxIndex], () => {
  resetPlaybackTimer();
});

function handleKeydown(e: KeyboardEvent) {
  if (e.key === " " || e.key === "Space") { e.preventDefault(); togglePlayback(); }
  if (e.key === "d" || e.key === "D") { showDiffs.value = !showDiffs.value; }
  if (e.key === "i" || e.key === "I") { showInfluence.value = !showInfluence.value; }
  if (e.key === "Escape") { focusedAgentId.value = ""; }
  if (e.key === "r" || e.key === "R") { createAndRunHexBattle(); }
}

onMounted(() => window.addEventListener("keydown", handleKeydown));
onUnmounted(() => {
  window.removeEventListener("keydown", handleKeydown);
  source.value?.close();
  clearPlaybackTimer();
});

async function ensureRoles() {
  if (!roles.value) {
    roles.value = await fetchRoles();
  }
}

let cancelled = false;

async function createAndRunHexBattle() {
  cancelled = false;
  loading.value = true;
  error.value = "";
  status.value = "creating";
  playing.value = false;
  source.value?.close();
  const timeout = setTimeout(() => {
    cancelled = true;
    loading.value = false;
    status.value = "error";
    error.value = "创建超时，请检查后端是否运行";
  }, 15000);
  try {
    await ensureRoles();
    if (cancelled) return;
    const teamConfig = roles.value?.default_team_config as TeamConfigPayload;
    const result = await createBattle({
      mode: "实时推演",
      max_turns: 36,
      team_config: teamConfig,
      scenario_config: { ...scenario.value, grid_type: "hex" },
    });
    if (cancelled) return;
    battleId.value = result.battle_id;
    frames.value = [result.initial_frame];
    currentIndex.value = 0;
    focusedAgentId.value = "";
    status.value = "running";
    await startBattle(result.battle_id, "实时推演");
    if (cancelled) return;
    source.value = openBattleStream(result.battle_id, {
      onFrame: (frame) => {
        if (cancelled) return;
        frames.value.push(frame);
        currentIndex.value = frames.value.length - 1;
      },
      onDone: () => {
        if (cancelled) return;
        status.value = "done";
        source.value?.close();
        source.value = null;
      },
      onError: (errMsg?: string) => {
        if (cancelled) return;
        status.value = "error";
        error.value = errMsg || "Hex Lab 实时流中断";
      },
    });
  } catch (err) {
    if (cancelled) return;
    status.value = "error";
    const msg = err instanceof Error ? err.message : String(err);
    try {
      const parsed = JSON.parse(msg);
      error.value = parsed.error || parsed.detail || msg;
    } catch {
      error.value = msg;
    }
  } finally {
    clearTimeout(timeout);
    loading.value = false;
  }
}

function seek(index: number) {
  currentIndex.value = Math.max(0, Math.min(maxIndex.value, index));
  playing.value = false;
}

function togglePlayback() {
  if (frames.value.length < 2) return;
  if (playing.value) {
    playing.value = false;
    return;
  }
  if (currentIndex.value >= maxIndex.value) currentIndex.value = 0;
  playing.value = true;
}

const AUTO_PAUSE_EVENTS = new Set(["RESULT", "DOWN", "ATTACK", "ENGAGE", "SKILL"]);

function checkAutoPause(index: number): boolean {
  const frame = frames.value[index];
  if (!frame) return false;
  return frame.timeline_markers?.some((m) => AUTO_PAUSE_EVENTS.has(m.type)) ?? false;
}

function resetPlaybackTimer() {
  clearPlaybackTimer();
  if (!playing.value) return;
  playbackTimer = window.setInterval(() => {
    if (currentIndex.value >= maxIndex.value) {
      playing.value = false;
      return;
    }
    const next = currentIndex.value + 1;
    if (checkAutoPause(next)) {
      currentIndex.value = next;
      playing.value = false;
      return;
    }
    currentIndex.value = next;
  }, Math.max(120, 700 / playbackSpeed.value));
}

function clearPlaybackTimer() {
  if (playbackTimer !== null) {
    window.clearInterval(playbackTimer);
    playbackTimer = null;
  }
}

function jumpToMarker(marker: { turn: number; actor_id?: string | null; target_id?: string | null }) {
  const index = frames.value.findIndex((frame) => frame.turn === marker.turn);
  if (index >= 0) currentIndex.value = index;
  focusedAgentId.value = marker.actor_id || marker.target_id || focusedAgentId.value;
}
</script>
