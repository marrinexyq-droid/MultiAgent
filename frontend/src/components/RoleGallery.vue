<template>
  <section class="section-card">
    <div class="section-head">
      <div>
        <div class="eyebrow">{{ team === "red" ? "Red Team" : "Blue Team" }}</div>
        <h2>{{ team === "red" ? "红队编成" : "蓝队编成" }}</h2>
      </div>
    </div>

    <div class="role-group-stack">
      <section v-for="group in groupedRoles" :key="group.key" class="role-group-block">
        <div class="role-group-head">
          <div class="eyebrow">{{ group.kicker }}</div>
          <h3>{{ group.label }}</h3>
        </div>
        <div class="role-grid grouped">
          <article v-for="role in group.roles" :key="role.role" class="role-card">
            <button type="button" class="role-card-surface" @click="deploymentStore.openRolePanel(team, role.role)">
              <div class="role-title-row">
                <div class="role-title">{{ role.label }}</div>
                <span class="role-skill">{{ role.skill_name }}</span>
              </div>
              <div class="role-desc">{{ role.description }}</div>
              <div class="role-desc subtle">{{ role.ui_hint }}</div>
              <div class="role-caption-row">
                <span class="role-caption">建议数量 {{ role.recommended_count }}</span>
                <span class="role-caption">{{ targetPreferenceText(role.role) }}</span>
              </div>
            </button>
            <div class="role-meta compact">
              <div class="count-stepper" @click.stop>
                <button type="button" class="stepper-btn" @click="deploymentStore.adjustCount(team, role.role, -1)">-</button>
                <strong>x{{ deploymentStore.teamConfig?.[team]?.[role.role]?.count ?? 0 }}</strong>
                <button type="button" class="stepper-btn" @click="deploymentStore.adjustCount(team, role.role, 1)">+</button>
              </div>
              <button type="button" class="role-link-btn" @click="deploymentStore.openRolePanel(team, role.role)">
                高级设置
              </button>
            </div>
            <div class="role-chip-row">
              <span class="role-mini-chip">偏好 {{ targetPreferenceText(role.role).replace("偏好 ", "") }}</span>
              <span class="role-mini-chip">队伍 {{ team === "red" ? "红" : "蓝" }}</span>
            </div>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useDeploymentStore } from "../stores/deployment";
import { useScenarioStore } from "../stores/scenario";
import type { RoleKey, TeamKey } from "../types";

const props = defineProps<{ team: TeamKey }>();
const deploymentStore = useDeploymentStore();
const scenarioStore = useScenarioStore();

const groupLabels = {
  core_combat: { label: "基础作战", kicker: "Core Combat" },
  command_support: { label: "指挥与支援", kicker: "Command Support" },
  special_tactics: { label: "特殊战术", kicker: "Special Tactics" },
} as const;

const groupedRoles = computed(() =>
  Object.entries(groupLabels).map(([groupKey, meta]) => ({
    key: groupKey,
    ...meta,
    roles: Object.values(scenarioStore.roles ?? {}).filter((role) => role.group === groupKey),
  })),
);

function targetPreferenceText(role: RoleKey) {
  const value = deploymentStore.teamConfig?.[props.team]?.[role]?.target_preference;
  return `偏好 ${targetPreferenceLabel(value ?? "balanced")}`;
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
</script>
