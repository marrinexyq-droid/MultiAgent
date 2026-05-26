import { defineStore } from "pinia";
import type { RectZone, RoleKey, ScenarioConfig, SelectedZoneRef, TeamConfigPayload, TeamKey } from "../types";
import { useScenarioStore } from "./scenario";

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function normalizeZone(zone: RectZone, bounds: { width: number; height: number }) {
  const maxWidth = Math.max(1, bounds.width);
  const maxHeight = Math.max(1, bounds.height);
  zone.width = clamp(Math.round(zone.width || 1), 1, maxWidth);
  zone.height = clamp(Math.round(zone.height || 1), 1, maxHeight);
  zone.x = clamp(Math.round(zone.x || 0), 0, Math.max(0, bounds.width - zone.width));
  zone.y = clamp(Math.round(zone.y || 0), 0, Math.max(0, bounds.height - zone.height));
}

function zonesForTeam(scenario: ScenarioConfig, team: TeamKey | "control") {
  return team === "red"
    ? scenario.red_spawn_zones
    : team === "blue"
      ? scenario.blue_spawn_zones
      : scenario.control_zones;
}

export const useDeploymentStore = defineStore("deployment", {
  state: () => ({
    teamConfig: null as TeamConfigPayload | null,
    scenarioConfig: null as ScenarioConfig | null,
    openPanel: null as { team: TeamKey; role: RoleKey } | null,
    selectedZone: null as SelectedZoneRef | null,
    mode: "实时推演",
    maxTurns: 40,
  }),
  actions: {
    async ensureDefaults() {
      const scenario = useScenarioStore();
      await scenario.ensureLoaded();
      if (!this.teamConfig && scenario.defaultTeamConfig) {
        this.teamConfig = JSON.parse(JSON.stringify(scenario.defaultTeamConfig));
        this.maxTurns = scenario.defaultMaxTurns;
      }
      if (!this.scenarioConfig && scenario.defaultScenarioConfig) {
        this.scenarioConfig = JSON.parse(JSON.stringify(scenario.defaultScenarioConfig));
      }
      this.ensureSelectedZone();
    },
    openRolePanel(team: TeamKey, role: RoleKey) {
      this.openPanel = { team, role };
    },
    closeRolePanel() {
      this.openPanel = null;
    },
    ensureSelectedZone() {
      if (!this.scenarioConfig) return;
      if (this.selectedZone) {
        const existing = zonesForTeam(this.scenarioConfig, this.selectedZone.team)[this.selectedZone.index];
        if (existing) return;
      }
      if (this.scenarioConfig.red_spawn_zones.length) {
        this.selectedZone = { team: "red", index: 0 };
        return;
      }
      if (this.scenarioConfig.blue_spawn_zones.length) {
        this.selectedZone = { team: "blue", index: 0 };
        return;
      }
      if (this.scenarioConfig.control_zones.length) {
        this.selectedZone = { team: "control", index: 0 };
      }
    },
    selectZone(team: TeamKey | "control", index: number) {
      if (!this.scenarioConfig) return;
      if (!zonesForTeam(this.scenarioConfig, team)[index]) return;
      this.selectedZone = { team, index };
    },
    adjustCount(team: TeamKey, role: RoleKey, delta: number) {
      if (!this.teamConfig) return;
      const current = this.teamConfig[team][role].count;
      this.teamConfig[team][role].count = Math.min(6, Math.max(0, current + delta));
    },
    updateRoleField(team: TeamKey, role: RoleKey, key: keyof TeamConfigPayload[TeamKey][RoleKey], value: number) {
      if (!this.teamConfig) return;
      this.teamConfig[team][role][key] = value as never;
    },
    updateRoleTextField(team: TeamKey, role: RoleKey, key: keyof TeamConfigPayload[TeamKey][RoleKey], value: string) {
      if (!this.teamConfig) return;
      this.teamConfig[team][role][key] = value as never;
    },
    updateScenarioField(key: keyof ScenarioConfig, value: ScenarioConfig[keyof ScenarioConfig]) {
      if (!this.scenarioConfig) return;
      (this.scenarioConfig[key] as ScenarioConfig[keyof ScenarioConfig]) = value;
      this.clampScenario();
    },
    setScenarioSize(width: number, height: number) {
      if (!this.scenarioConfig) return;
      this.scenarioConfig.width = clamp(Math.round(width), 6, 24);
      this.scenarioConfig.height = clamp(Math.round(height), 6, 24);
      this.clampScenario();
    },
    clampScenario() {
      if (!this.scenarioConfig) return;
      const bounds = { width: this.scenarioConfig.width, height: this.scenarioConfig.height };
      this.scenarioConfig.red_spawn_zones.forEach((zone) => normalizeZone(zone, bounds));
      this.scenarioConfig.blue_spawn_zones.forEach((zone) => normalizeZone(zone, bounds));
      this.scenarioConfig.control_zones.forEach((zone) => normalizeZone(zone, bounds));
      this.ensureSelectedZone();
    },
    updateZone(team: TeamKey | "control", index: number, field: "x" | "y" | "width" | "height", value: number) {
      if (!this.scenarioConfig) return;
      const zones = zonesForTeam(this.scenarioConfig, team);
      if (!zones[index]) return;
      zones[index][field] = Math.max(0, Math.round(value));
      normalizeZone(zones[index], { width: this.scenarioConfig.width, height: this.scenarioConfig.height });
      this.selectedZone = { team, index };
    },
    moveZone(team: TeamKey | "control", index: number, x: number, y: number) {
      if (!this.scenarioConfig) return;
      const zones = zonesForTeam(this.scenarioConfig, team);
      if (!zones[index]) return;
      zones[index].x = x;
      zones[index].y = y;
      normalizeZone(zones[index], { width: this.scenarioConfig.width, height: this.scenarioConfig.height });
      this.selectedZone = { team, index };
    },
    replaceZone(team: TeamKey | "control", index: number, patch: Partial<RectZone>) {
      if (!this.scenarioConfig) return;
      const zones = zonesForTeam(this.scenarioConfig, team);
      if (!zones[index]) return;
      Object.assign(zones[index], patch);
      normalizeZone(zones[index], { width: this.scenarioConfig.width, height: this.scenarioConfig.height });
      this.selectedZone = { team, index };
    },
  },
});
