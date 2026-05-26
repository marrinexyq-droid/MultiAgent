<template>
  <Teleport to="body">
    <div v-if="isOpen && currentRole && currentConfig" class="drawer-backdrop" @click="closeDrawer">
      <aside class="settings-drawer" @click.stop>
        <div class="drawer-head">
          <div>
            <div class="eyebrow">Advanced Role Tuning</div>
            <h2>{{ currentRole.label }}</h2>
            <p>{{ teamLabel }} / {{ currentRole.skill_name }}</p>
          </div>
          <button type="button" class="ghost-btn" @click="closeDrawer">关闭</button>
        </div>

        <section class="drawer-section">
          <div class="drawer-meta-grid">
            <div class="meta-card">
              <span>当前数量</span>
              <strong>x{{ currentConfig.count }}</strong>
            </div>
            <div class="meta-card">
              <span>角色定位</span>
              <strong>{{ currentRole.description }}</strong>
            </div>
          </div>
          <p class="panel-copy">{{ currentRole.skill_description }}</p>
          <p class="panel-copy subtle">{{ currentRole.ui_hint }}</p>
        </section>

        <section class="drawer-section">
          <div class="drawer-section-head">
            <div class="eyebrow">Core Attributes</div>
            <strong>核心属性</strong>
          </div>
          <div class="advanced-grid">
            <div class="slider-group">
              <label>数量: {{ currentConfig.count }}</label>
              <input
                type="range"
                min="0"
                max="6"
                step="1"
                :value="currentConfig.count"
                @input="updateField('count', Number(($event.target as HTMLInputElement).value))"
              />
            </div>
            <div v-for="field in statFields" :key="field.key" class="slider-group">
              <label>{{ field.label }}: {{ currentConfig[field.key] }}</label>
              <input
                :min="field.min"
                :max="field.max"
                :step="field.step"
                type="range"
                :value="currentConfig[field.key]"
                @input="updateField(field.key, Number(($event.target as HTMLInputElement).value))"
              />
            </div>
          </div>
        </section>

        <section class="drawer-section">
          <div class="drawer-section-head">
            <div class="eyebrow">Behavior Bias</div>
            <strong>行为偏好</strong>
          </div>
          <div class="advanced-grid">
            <div class="slider-group">
              <label>目标偏好</label>
              <select
                class="panel-select"
                :value="currentConfig.target_preference"
                @change="updateTextField('target_preference', ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="option in currentRole.target_preference_options" :key="option" :value="option">
                  {{ targetPreferenceLabel(option) }}
                </option>
              </select>
            </div>
            <div v-for="field in preferenceFields" :key="field.key" class="slider-group">
              <label>{{ field.label }}: {{ currentConfig[field.key] }}</label>
              <input
                :min="field.min"
                :max="field.max"
                :step="field.step"
                type="range"
                :value="currentConfig[field.key]"
                @input="updateField(field.key, Number(($event.target as HTMLInputElement).value))"
              />
            </div>
          </div>
        </section>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from "vue";
import { useDeploymentStore } from "../stores/deployment";
import { useScenarioStore } from "../stores/scenario";
import type { RoleKey, TeamRoleConfig } from "../types";

const deploymentStore = useDeploymentStore();
const scenarioStore = useScenarioStore();

const isOpen = computed(() => Boolean(deploymentStore.openPanel));
const currentTeam = computed(() => deploymentStore.openPanel?.team ?? "red");
const currentRole = computed(() => {
  const role = deploymentStore.openPanel?.role;
  return role ? scenarioStore.roles?.[role] : null;
});
const currentConfig = computed(() => {
  const role = deploymentStore.openPanel?.role;
  const team = deploymentStore.openPanel?.team;
  return role && team ? deploymentStore.teamConfig?.[team]?.[role] ?? null : null;
});
const teamLabel = computed(() => (currentTeam.value === "red" ? "红队" : "蓝队"));

const statFields = computed(() => {
  const role = currentRole.value;
  if (!role) return [];
  return [
    { key: "hp", label: "生命", min: role.bounds.hp[0], max: role.bounds.hp[1], step: 5 },
    { key: "ammo", label: "资源", min: role.bounds.ammo[0], max: role.bounds.ammo[1], step: 1 },
    { key: "vision_range", label: "视野", min: role.bounds.vision_range[0], max: role.bounds.vision_range[1], step: 1 },
    { key: "attack_power", label: "攻击", min: role.bounds.attack_power[0], max: role.bounds.attack_power[1], step: 1 },
    { key: "move_speed", label: "移动力", min: role.bounds.move_speed[0], max: role.bounds.move_speed[1], step: 1 },
  ] as Array<{ key: keyof TeamRoleConfig; label: string; min: number; max: number; step: number }>;
});

const preferenceFields = computed(() => {
  const role = currentRole.value;
  if (!role) return [];
  const [min, max] = role.bounds.preference;
  return [
    { key: "task_priority", label: "任务优先级", min, max, step: 5 },
    { key: "risk_preference", label: "风险偏好", min, max, step: 5 },
    { key: "coordination_preference", label: "协同偏好", min, max, step: 5 },
    { key: "mobility_bias", label: "机动倾向", min, max, step: 5 },
    { key: "hold_bias", label: "守点倾向", min, max, step: 5 },
    { key: "skill_trigger_threshold", label: "技能阈值", min, max, step: 5 },
  ] as Array<{ key: keyof TeamRoleConfig; label: string; min: number; max: number; step: number }>;
});

function closeDrawer() {
  deploymentStore.closeRolePanel();
}

function updateField(key: keyof TeamRoleConfig, value: number) {
  const role = deploymentStore.openPanel?.role;
  const team = deploymentStore.openPanel?.team;
  if (!role || !team) return;
  deploymentStore.updateRoleField(team, role, key, value);
}

function updateTextField(key: keyof TeamRoleConfig, value: string) {
  const role = deploymentStore.openPanel?.role;
  const team = deploymentStore.openPanel?.team;
  if (!role || !team) return;
  deploymentStore.updateRoleTextField(team, role, key, value);
}

function targetPreferenceLabel(value: string) {
  return {
    balanced: "均衡",
    frontline: "前线",
    backline: "后排",
    marked: "标记目标",
    control: "控制区",
  }[value] ?? value;
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") {
    closeDrawer();
  }
}

onMounted(() => {
  window.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
});
</script>
