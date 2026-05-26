<template>
  <main class="page">
    <section class="hero compact deployment-hero">
      <div>
        <div class="eyebrow">Deployment Console</div>
        <h1>战备部署</h1>
        <p>先配置红蓝阵容，再在沙盘里调整出生区与控制区，最后一键创建 battle session。</p>
      </div>
      <div class="deployment-launchbar section-card">
        <label>
          模式
          <select v-model="deploymentStore.mode">
            <option>实时推演</option>
            <option>演练后回放</option>
          </select>
        </label>
        <label>
          最大回合数
          <input v-model="deploymentStore.maxTurns" type="number" min="10" max="80" step="5" />
        </label>
        <button class="primary-btn" :disabled="battleStore.loading || scenarioStore.loading || !deploymentStore.teamConfig || !deploymentStore.scenarioConfig" @click="launchBattle">创建演练</button>
      </div>
    </section>
    <section v-if="deploymentStore.teamConfig && deploymentStore.scenarioConfig" class="section-card deployment-overview">
      <div class="section-head">
        <div>
          <div class="eyebrow">Overview</div>
          <h2>部署全局预览</h2>
        </div>
      </div>
      <div class="overview-grid">
        <div class="meta-card team-red-soft">
          <span>红队总兵力</span>
          <strong>{{ teamUnitCount("red") }}</strong>
          <small>{{ roleBreakdown("red") }}</small>
        </div>
        <div class="meta-card team-blue-soft">
          <span>蓝队总兵力</span>
          <strong>{{ teamUnitCount("blue") }}</strong>
          <small>{{ roleBreakdown("blue") }}</small>
        </div>
        <div class="meta-card">
          <span>演练模式</span>
          <strong>{{ deploymentStore.mode }}</strong>
          <small>默认从当前配置直接创建 battle session</small>
        </div>
        <div class="meta-card">
          <span>最大回合数</span>
          <strong>{{ deploymentStore.maxTurns }}</strong>
          <small>{{ strengthDelta }}</small>
        </div>
        <div class="meta-card">
          <span>地图尺寸</span>
          <strong>{{ deploymentStore.scenarioConfig.width }} × {{ deploymentStore.scenarioConfig.height }}</strong>
          <small>{{ zoneSummary("control") }}</small>
        </div>
        <div class="meta-card">
          <span>出生区</span>
          <strong>红 {{ zoneSummary("red") }} / 蓝 {{ zoneSummary("blue") }}</strong>
          <small>可在下方场景配置卡中调整</small>
        </div>
      </div>
    </section>
    <section v-if="scenarioStore.error || battleStore.error" class="section-card error-card">
      <div class="section-head">
        <div><div class="eyebrow">Connection</div><h2>连接异常</h2></div>
      </div>
      <p v-if="scenarioStore.error">角色模板加载失败：{{ scenarioStore.error }}</p>
      <p v-if="battleStore.error">创建演练失败：{{ battleStore.error }}</p>
      <p>请确认后端 API 已启动：<code>./venv/bin/python -m src.battle.api_server</code></p>
    </section>
    <section v-else-if="scenarioStore.loading" class="section-card">
      <div class="empty-state">正在加载角色模板和默认阵容...</div>
    </section>
    <ScenarioEditor v-if="deploymentStore.scenarioConfig" />
    <div class="gallery-grid" v-if="scenarioStore.roles && deploymentStore.teamConfig">
      <RoleGallery team="red" />
      <RoleGallery team="blue" />
    </div>
    <section v-else-if="!scenarioStore.loading" class="section-card">
      <div class="empty-state">当前没有加载到阵容配置。通常这是因为后端 API 没有启动，或前端连不到 <code>{{ apiBase }}</code>。</div>
    </section>
    <RoleSettingsDrawer />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import RoleGallery from "../components/RoleGallery.vue";
import RoleSettingsDrawer from "../components/RoleSettingsDrawer.vue";
import ScenarioEditor from "../components/ScenarioEditor.vue";
import { useBattleStore } from "../stores/battle";
import { useDeploymentStore } from "../stores/deployment";
import { useScenarioStore } from "../stores/scenario";
import type { TeamKey } from "../types";

const scenarioStore = useScenarioStore();
const deploymentStore = useDeploymentStore();
const battleStore = useBattleStore();
const router = useRouter();
const apiBase = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

onMounted(async () => {
  try {
    await scenarioStore.ensureLoaded();
    await deploymentStore.ensureDefaults();
  } catch {
    // Error state is surfaced in the page.
  }
});

const roleLabelMap = {
  coordinator: "协调",
  scout: "侦察",
  attacker: "攻击手",
  defender: "防御手",
  support: "支援",
  jammer: "干扰",
  controller: "控制",
  assaulter: "突击",
} as const;

function teamUnitCount(team: TeamKey) {
  const config = deploymentStore.teamConfig?.[team];
  if (!config) return 0;
  return Object.values(config).reduce((sum, item) => sum + item.count, 0);
}

function roleBreakdown(team: TeamKey) {
  const config = deploymentStore.teamConfig?.[team];
  if (!config) return "暂无编成";
  return Object.entries(config)
    .filter(([, item]) => item.count > 0)
    .map(([role, item]) => `${roleLabelMap[role as keyof typeof roleLabelMap]} x${item.count}`)
    .join(" / ") || "暂无编成";
}

const strengthDelta = computed(() => {
  const red = teamUnitCount("red");
  const blue = teamUnitCount("blue");
  if (red === blue) return "当前红蓝兵力平衡";
  return red > blue ? `红队兵力领先 ${red - blue}` : `蓝队兵力领先 ${blue - red}`;
});

function zoneSummary(team: "red" | "blue" | "control") {
  const scenario = deploymentStore.scenarioConfig;
  if (!scenario) return "-";
  const zones =
    team === "red" ? scenario.red_spawn_zones :
    team === "blue" ? scenario.blue_spawn_zones :
    scenario.control_zones;
  return zones.map((zone) => `${zone.width}×${zone.height}@(${zone.x},${zone.y})`).join(" / ");
}

async function launchBattle() {
  try {
    await battleStore.createFromDeployment();
    if (deploymentStore.mode === "实时推演") {
      router.push(`/battle/${battleStore.battleId}`);
    } else {
      router.push(`/review/${battleStore.battleId}`);
    }
  } catch {
    // Error state is surfaced in the page.
  }
}
</script>
