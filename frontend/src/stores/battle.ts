import { defineStore } from "pinia";
import { createBattle, fetchBattleFrames, fetchBattleSummary, openBattleStream, startBattle } from "../api";
import type { BattleFrame } from "../types";
import { useDeploymentStore } from "./deployment";

export const useBattleStore = defineStore("battle", {
  state: () => ({
    battleId: "" as string,
    mode: "实时推演",
    status: "idle",
    frames: [] as BattleFrame[],
    currentTurn: 0,
    summary: null as unknown,
    source: null as EventSource | null,
    loading: false,
    error: "" as string,
    focusedAgentId: "" as string,
    hoveredAgentId: "" as string,
    isPlaying: false,
    playbackSpeed: 1,
  }),
  getters: {
    currentFrame(state) {
      return state.frames[state.currentTurn] ?? null;
    },
    focusedUnit(state) {
      const frame = state.frames[state.currentTurn] ?? null;
      if (!frame || !state.focusedAgentId) return null;
      return frame.units.find((unit) => unit.agent_id === state.focusedAgentId) ?? null;
    },
    hoveredUnit(state) {
      const frame = state.frames[state.currentTurn] ?? null;
      if (!frame || !state.hoveredAgentId) return null;
      return frame.units.find((unit) => unit.agent_id === state.hoveredAgentId) ?? null;
    },
    timelineMarkers(state) {
      return state.frames.flatMap((frame) => frame.timeline_markers ?? []);
    },
  },
  actions: {
    async createFromDeployment() {
      const deployment = useDeploymentStore();
      if (!deployment.teamConfig || !deployment.scenarioConfig) throw new Error("missing deployment config");
      this.loading = true;
      this.error = "";
      try {
        const result = await createBattle({
          mode: deployment.mode,
          max_turns: deployment.maxTurns,
          team_config: deployment.teamConfig,
          scenario_config: deployment.scenarioConfig,
        });
        this.battleId = result.battle_id;
        this.mode = deployment.mode;
        this.frames = [result.initial_frame];
        this.currentTurn = 0;
        this.status = "created";
        this.focusedAgentId = "";
        this.hoveredAgentId = "";
        this.isPlaying = false;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "创建演练失败";
        throw error;
      } finally {
        this.loading = false;
      }
    },
    async startRealtime() {
      if (!this.battleId) throw new Error("missing battle id");
      this.status = "running";
      this.error = "";
      this.isPlaying = false;
      await startBattle(this.battleId, "实时推演");
      this.source?.close();
      this.source = openBattleStream(this.battleId, {
        onFrame: (frame, summary) => {
          this.frames.push(frame);
          this.currentTurn = this.frames.length - 1;
          this.summary = summary;
        },
        onDone: async (payload) => {
          this.status = "done";
          this.isPlaying = false;
          this.summary = (payload as { result?: unknown })?.result ?? payload ?? await fetchBattleSummary(this.battleId);
          this.source?.close();
          this.source = null;
        },
        onError: () => {
          if (this.status === "done") {
            return;
          }
          this.error = "实时推演流中断";
          this.status = "error";
          this.isPlaying = false;
        },
      });
    },
    async loadReplay() {
      if (!this.battleId) throw new Error("missing battle id");
      this.loading = true;
      try {
        const result = await fetchBattleFrames(this.battleId);
        this.frames = result.frames;
        this.summary = result.summary;
        this.currentTurn = Math.max(0, result.frames.length - 1);
        this.status = "done";
        this.isPlaying = false;
      } finally {
        this.loading = false;
      }
    },
    play() {
      if (this.frames.length < 2) return;
      if (this.currentTurn >= this.frames.length - 1) {
        this.currentTurn = 0;
      }
      this.isPlaying = true;
    },
    pause() {
      this.isPlaying = false;
    },
    togglePlayback() {
      if (this.isPlaying) {
        this.pause();
      } else {
        this.play();
      }
    },
    stepForward() {
      this.pause();
      this.currentTurn = Math.min(Math.max(0, this.frames.length - 1), this.currentTurn + 1);
    },
    stepBackward() {
      this.pause();
      this.currentTurn = Math.max(0, this.currentTurn - 1);
    },
    seekToStart() {
      this.pause();
      this.currentTurn = 0;
    },
    seekToLatest() {
      this.pause();
      this.currentTurn = Math.max(0, this.frames.length - 1);
    },
    setPlaybackSpeed(speed: number) {
      this.playbackSpeed = speed;
    },
    setFocusedAgent(agentId: string) {
      this.focusedAgentId = agentId;
    },
    setHoveredAgent(agentId: string) {
      this.hoveredAgentId = agentId;
    },
  },
});
