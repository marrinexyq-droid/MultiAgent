import type { BattleFrame, RolesResponse, ScenarioConfig, TeamConfigPayload } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function fetchRoles(): Promise<RolesResponse> {
  const response = await fetch(`${API_BASE}/api/roles`);
  if (!response.ok) throw new Error("failed to load roles");
  return response.json();
}

export async function createBattle(payload: {
  mode: string;
  max_turns: number;
  team_config: TeamConfigPayload;
  scenario_config: ScenarioConfig;
}): Promise<{ battle_id: string; initial_frame: BattleFrame; mode: string; max_turns: number; scenario_config: ScenarioConfig }> {
  const response = await fetch(`${API_BASE}/api/battles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("failed to create battle");
  return response.json();
}

export async function startBattle(battleId: string, mode: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/battles/${battleId}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!response.ok) throw new Error("failed to start battle");
}

export function openBattleStream(
  battleId: string,
  handlers: {
    onFrame: (frame: BattleFrame, summary: unknown) => void;
    onDone: (payload: unknown) => void;
    onError: (error: Event) => void;
  },
): EventSource {
  const source = new EventSource(`${API_BASE}/api/battles/${battleId}/stream`);
  source.addEventListener("frame", (event) => {
    const payload = JSON.parse((event as MessageEvent).data);
    handlers.onFrame(payload.frame, payload.summary);
  });
  source.addEventListener("done", (event) => {
    handlers.onDone(JSON.parse((event as MessageEvent).data));
    source.close();
  });
  source.onerror = (event) => {
    if (source.readyState === EventSource.CLOSED) {
      return;
    }
    handlers.onError(event);
  };
  return source;
}

export async function fetchBattleFrames(battleId: string): Promise<{ frames: BattleFrame[]; summary: unknown }> {
  const response = await fetch(`${API_BASE}/api/battles/${battleId}/frames`);
  if (!response.ok) throw new Error("failed to load frames");
  return response.json();
}

export async function fetchBattleSummary(battleId: string): Promise<unknown> {
  const response = await fetch(`${API_BASE}/api/battles/${battleId}/summary`);
  if (!response.ok) throw new Error("failed to load summary");
  return response.json();
}
