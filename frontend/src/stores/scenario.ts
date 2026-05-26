import { defineStore } from "pinia";
import { fetchRoles } from "../api";
import type { RolesResponse } from "../types";

export const useScenarioStore = defineStore("scenario", {
  state: () => ({
    rolesResponse: null as RolesResponse | null,
    loading: false,
    error: "" as string,
  }),
  getters: {
    roles: (state) => state.rolesResponse?.roles ?? null,
    defaultTeamConfig: (state) => state.rolesResponse?.default_team_config ?? null,
    defaultMaxTurns: (state) => state.rolesResponse?.default_max_turns ?? 40,
    defaultScenarioConfig: (state) => state.rolesResponse?.default_scenario_config ?? null,
  },
  actions: {
    async ensureLoaded() {
      if (this.rolesResponse) return;
      this.loading = true;
      this.error = "";
      try {
        this.rolesResponse = await fetchRoles();
      } catch (error) {
        this.error = error instanceof Error ? error.message : "加载角色模板失败";
        throw error;
      } finally {
        this.loading = false;
      }
    },
  },
});
