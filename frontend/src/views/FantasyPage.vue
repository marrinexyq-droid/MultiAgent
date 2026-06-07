<template>
  <main class="fantasy-page">
    <section class="fantasy-topbar">
      <div>
        <div class="fantasy-eye">✦ FANTASY BATTLE ✦</div>
        <h1>魔幻试验场</h1>
        <p>8 人小队对抗：1MT 1ST 4D 2N · 自动战斗 · 施法读条</p>
      </div>
      <div class="fantasy-actions">
        <RouterLink class="fantasy-btn secondary" to="/hex-lab">← 返回六边形</RouterLink>
        <button class="fantasy-btn primary" :disabled="loading" @click="createBattle">{{ battleId ? "✦ 重新创建" : "✦ 创建演练" }}</button>
      </div>
    </section>

    <section class="fantasy-console">
      <div class="fantasy-main">
        <FantasyMap :frame="currentFrame" :turn="currentTurn" :focused-id="focusedAgentId" :cast-bars="castBars" @cell-click="onCellClick" />
      </div>

      <aside class="fantasy-side">
        <div class="fantasy-card" v-if="currentFrame">
          <div class="fantasy-card-title">🏰 战况</div>
          <div class="fantasy-stats">
            <span>🔴 红 {{ redAlive }}/8</span>
            <span>🔵 蓝 {{ blueAlive }}/8</span>
            <span>T{{ currentTurn }}</span>
          </div>
          <div class="fantasy-hp-bars">
            <div class="fantasy-bar-row"><span>🔴</span><div class="bar"><div class="bar-fill bar-red" :style="{ width: redPct + '%' }"></div></div><span>{{ redAlive }}/8</span></div>
            <div class="fantasy-bar-row"><span>🔵</span><div class="bar"><div class="bar-fill bar-blue" :style="{ width: bluePct + '%' }"></div></div><span>{{ blueAlive }}/8</span></div>
          </div>
          <div class="fantasy-battle-log" v-if="battleLog.length">
            <div v-for="(log, i) in battleLog.slice(-6)" :key="i" class="fantasy-log-line" :class="logClass(log)">{{ log.text }}</div>
          </div>
        </div>

        <div class="fantasy-card" v-if="currentFrame?.stats?.length">
          <div class="fantasy-card-title">📊 战斗统计</div>
          <div class="stat-section">
            <div class="stat-section-label">DPS</div>
            <div v-for="s in sortedStats('dps')" :key="s.agent_id" class="stat-row" :class="{ dead: !s.alive }">
              <span class="stat-icon">{{ s.icon }}</span>
              <span class="stat-name">{{ s.role_label }}</span>
              <span class="stat-team" :class="`team-${s.team}`">{{ s.team === 'red' ? '🔴' : '🔵' }}</span>
              <div class="stat-bar"><div class="stat-bar-fill bar-dps" :style="{ width: statPct(s.dps, 'dps') + '%' }"></div></div>
              <span class="stat-val">{{ s.dps }}</span>
            </div>
          </div>
          <div class="stat-section">
            <div class="stat-section-label">HPS</div>
            <div v-for="s in sortedStats('hps')" :key="s.agent_id" class="stat-row" :class="{ dead: !s.alive }">
              <span class="stat-icon">{{ s.icon }}</span>
              <span class="stat-name">{{ s.role_label }}</span>
              <span class="stat-team" :class="`team-${s.team}`">{{ s.team === 'red' ? '🔴' : '🔵' }}</span>
              <div class="stat-bar"><div class="stat-bar-fill bar-hps" :style="{ width: statPct(s.hps, 'hps') + '%' }"></div></div>
              <span class="stat-val">{{ s.hps }}</span>
            </div>
          </div>
          <div class="stat-section">
            <div class="stat-section-label">承伤</div>
            <div v-for="s in sortedStats('damage_taken')" :key="s.agent_id" class="stat-row" :class="{ dead: !s.alive }">
              <span class="stat-icon">{{ s.icon }}</span>
              <span class="stat-name">{{ s.role_label }}</span>
              <span class="stat-team" :class="`team-${s.team}`">{{ s.team === 'red' ? '🔴' : '🔵' }}</span>
              <div class="stat-bar"><div class="stat-bar-fill bar-taken" :style="{ width: statPct(s.damage_taken, 'taken') + '%' }"></div></div>
              <span class="stat-val">{{ s.damage_taken }}</span>
            </div>
          </div>
        </div>

        <div class="fantasy-card" v-if="focusedUnit">
          <div class="fantasy-card-title">{{ focusedUnit.icon }} {{ focusedUnit.role_label }}</div>
          <div class="fantasy-unit-detail">
            <div><span>HP</span><strong>{{ focusedUnit.hp }}/{{ focusedUnit.max_hp }}</strong></div>
            <div><span>ATK</span><strong>{{ focusedUnit.attack_power }}</strong></div>
            <div><span>位置</span><strong>({{ focusedUnit.pos.x }},{{ focusedUnit.pos.y }})</strong></div>
            <div><span>状态</span><strong>{{ focusedUnit.alive ? '存活' : '阵亡' }}</strong></div>
            <div v-if="focusedUnit.resources && Object.keys(focusedUnit.resources).length"><span>资源</span><strong>{{ formatResources(focusedUnit.resources) }}</strong></div>
          </div>
        </div>

        <div class="fantasy-card" v-if="currentFrame?.team_lb">
          <div class="fantasy-card-title">⚡ 极限技</div>
          <div class="lb-row"><span class="lb-label">🔴</span><div class="lb-track"><div class="lb-fill lb-red" :style="{ width: redLB + '%' }"></div></div><span class="lb-val">{{ redLB }}%</span></div>
          <div class="lb-row"><span class="lb-label">🔵</span><div class="lb-track"><div class="lb-fill lb-blue" :style="{ width: blueLB + '%' }"></div></div><span class="lb-val">{{ blueLB }}%</span></div>
        </div>

        <div v-if="battleEnded" class="fantasy-card">
          <div class="fantasy-card-title">🏁 战斗结束</div>
          <div class="fantasy-result">{{ battleResult }}</div>
          <div class="fantasy-mvp" v-if="mvpData">🏆 MVP: {{ mvpData.icon }} {{ mvpData.role_label }} (DPS {{ mvpData.dps }})</div>
        </div>

        <div class="fantasy-speed-control">
          <span class="speed-label">速度</span>
          <div class="speed-btns">
            <button :class="{ active: speed === 0.5 }" @click="speed = 0.5">0.5x</button>
            <button :class="{ active: speed === 1 }" @click="speed = 1">1x</button>
            <button :class="{ active: speed === 2 }" @click="speed = 2">2x</button>
          </div>
        </div>

        <div v-if="currentFrame && !isAuto && !battleEnded" class="fantasy-actions-vertical">
          <button class="fantasy-btn primary" @click="startAutoBattle">⚔ 开始战斗</button>
        </div>
        <div v-else-if="isAuto && !battleEnded" class="fantasy-actions-vertical">
          <button class="fantasy-btn secondary" @click="stopAutoBattle">⏹ 暂停</button>
          <span class="fantasy-battle-status">战斗中... {{ currentTurn }}回合</span>
        </div>
      </aside>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, ref, onUnmounted } from "vue";
import { RouterLink } from "vue-router";
import FantasyMap from "../components/FantasyMap.vue";

const API = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const battleId = ref("");
const loading = ref(false);
const frames = ref<any[]>([]);
const currentTurn = ref(0);
const focusedAgentId = ref("");
const isAuto = ref(false);
const speed = ref(1);
const battleLog = ref<string[]>([]);
const castBars = ref<Array<{ agentId: string; skillName: string; pct: number }>>([]);
let autoTimer: ReturnType<typeof setInterval> | null = null;

const currentFrame = computed(() => frames.value[currentTurn.value] ?? null);
const focusedUnit = computed(() => currentFrame.value?.units?.find((u: any) => u.agent_id === focusedAgentId.value) ?? null);
const battleEnded = computed(() => {
  const f = currentFrame.value;
  if (!f?.units) return false;
  const ra = f.units.filter((u: any) => u.team === "red" && u.alive).length;
  const ba = f.units.filter((u: any) => u.team === "blue" && u.alive).length;
  return ra === 0 || ba === 0 || (currentTurn.value > 0 && ra + ba === 0);
});
const battleResult = computed(() => {
  const f = currentFrame.value;
  if (!f?.units) return "";
  const ra = f.units.filter((u: any) => u.team === "red" && u.alive).length;
  const ba = f.units.filter((u: any) => u.team === "blue" && u.alive).length;
  if (ra === 0 && ba === 0) return "平局! 双方团灭";
  if (ra === 0) return "🔵 蓝队 获胜!";
  if (ba === 0) return "🔴 红队 获胜!";
  return "";
});
const mvpData = computed(() => {
  const st = currentFrame.value?.stats ?? [];
  return st.sort((a: any, b: any) => b.dps - a.dps)[0] || null;
});
const redLB = computed(() => currentFrame.value?.team_lb?.red ?? 0);
const redAlive = computed(() => currentFrame.value?.units?.filter((u: any) => u.team === "red" && u.alive).length ?? 0);
const blueAlive = computed(() => currentFrame.value?.units?.filter((u: any) => u.team === "blue" && u.alive).length ?? 0);
const redPct = computed(() => (redAlive.value / 8) * 100);
const bluePct = computed(() => (blueAlive.value / 8) * 100);

onUnmounted(() => stopAutoBattle());

async function createBattle() {
  stopAutoBattle();
  loading.value = true;
  try {
    const resp = await fetch(`${API}/api/fantasy/create`, { method: "POST" });
    const data = await resp.json();
    battleId.value = data.battle_id;
    frames.value = [data.frame];
    currentTurn.value = 0;
    battleLog.value = [];
  } catch { alert("后端未启动"); }
  finally { loading.value = false; }
}

async function stepOnce(): Promise<boolean> {
  try {
    const resp = await fetch(`${API}/api/fantasy/step/${battleId.value}`, { method: "POST" });
    const data = await resp.json();
    frames.value.push(data.frame);
    currentTurn.value = frames.value.length - 1;
    const evs = data.frame.events_structured || [];
    for (const ev of evs.slice(0, 3)) {
      const meta = ev.metadata || {};
      let type = ev.type;
      if (meta.effect === "aoe_pending") type = "DANGER";
      else if (meta.effect === "heal") type = "HEAL";
      battleLog.value.push({ text: ev.summary || "", type, effect: meta.effect || "" });
    }
    if (data.done) {
      stopAutoBattle();
      battleLog.value.push("🏁 战斗结束");
      return true;
    }
    return false;
  } catch { stopAutoBattle(); return true; }
}

function simulateCasting(duration: number): Promise<void> {
  return new Promise((resolve) => {
    const steps = Math.max(3, Math.floor(duration / 300));
    let i = 0;
    const t = setInterval(() => {
      i++;
      castBars.value = [{ agentId: "system", skillName: "战斗中", pct: Math.round((i / steps) * 100) }];
      if (i >= steps) { clearInterval(t); castBars.value = []; resolve(); }
    }, Math.max(50, duration / steps));
  });
}

async function startAutoBattle() {
  if (isAuto.value) return;
  isAuto.value = true;
  while (isAuto.value) {
    const done = await stepOnce();
    if (done) break;
    const danger = currentFrame.value?.danger_zones?.length ?? 0;
    const base = danger > 0 ? 1500 : 1000;
    await simulateCasting(base / speed.value);
  }
  isAuto.value = false;
}

function stopAutoBattle() {
  isAuto.value = false;
  if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
  castBars.value = [];
}

function logClass(log: any): string {
  if (log.type === "HEAL" || log.effect === "heal") return "log-heal";
  if (log.type === "ATTACK") return "log-attack";
  if (log.type === "RESULT") return "log-result";
  if (log.type === "DANGER") return "log-danger";
  if (log.type === "LB") return "log-lb";
  return "";
}
function formatResources(res: Record<string, number>): string {
  const labels: Record<string, string> = { dark_blood: "暗血", chakra: "斗气", fire_stance: "火势", song: "诗心" };
  return Object.entries(res).map(([k, v]) => `${labels[k] || k}: ${v}`).join(" ");
}
function teamStats(team: string) {
  return currentFrame.value?.stats?.filter((s: any) => s.team === team) ?? [];
}
const statMax = (field: string) => Math.max(1, ...(currentFrame.value?.stats ?? []).map((s: any) => s[field] || 0));
const sortedStats = (field: string) => [...(currentFrame.value?.stats ?? [])].sort((a: any, b: any) => { if (a.alive !== b.alive) return a.alive ? -1 : 1; return b[field] - a[field]; });
const statPct = (val: number, field: string) => (val / statMax(field)) * 100;
function onCellClick(cell: any) {
  if (cell.unit) focusedAgentId.value = cell.unit.agent_id;
}
</script>

<style scoped>
.fantasy-page {
  min-height: calc(100vh - 82px);
  padding: 22px;
  background: linear-gradient(135deg, #0e0518, #1a0a2e, #0e0518);
}
.fantasy-topbar {
  max-width: 1560px; margin: 0 auto 18px; display: flex; justify-content: space-between; align-items: flex-end; gap: 18px;
  min-width: 0;
}
.fantasy-eye { font-size: 10px; font-weight: 700; color: #c8a878; letter-spacing: 0.3em; font-family: 'Space Mono', monospace; }
.fantasy-topbar h1 { margin: 4px 0 6px; font-size: clamp(32px, 4vw, 56px); color: #e8d8b8; letter-spacing: -0.06em; font-weight: 900; }
.fantasy-topbar p { margin: 0; color: rgba(200,168,120,0.5); font-size: 13px; max-width: 68ch; }
.fantasy-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.fantasy-actions-vertical { display: flex; flex-direction: column; gap: 8px; align-items: stretch; }
.fantasy-btn {
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 999px; padding: 10px 18px; font-size: 12px; font-weight: 700; cursor: pointer; border: none;
  font-family: 'Space Mono', monospace; transition: all 150ms ease; text-align: center;
}
.fantasy-btn.primary { background: linear-gradient(135deg, #c8a878, #a88858); color: #1a0a2e; box-shadow: 0 4px 16px rgba(200,168,120,0.25); }
.fantasy-btn.primary:disabled { opacity: 0.5; cursor: not-allowed; }
.fantasy-btn.secondary { background: transparent; color: rgba(200,168,120,0.6); border: 1px solid rgba(200,168,120,0.15); text-decoration: none; }
.fantasy-btn.secondary:hover { color: #c8a878; }

.fantasy-console {
  max-width: 1560px; margin: 0 auto; display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 320px);
  gap: 18px; height: clamp(560px, calc(100vh - 200px), 920px); min-height: 0;
}
.fantasy-main { min-height: 0; display: grid; }
.fantasy-side { display: grid; gap: 12px; align-content: start; overflow-y: auto; max-height: 100%; padding-right: 4px; }
.fantasy-card { background: rgba(30,15,50,0.6); border: 1px solid rgba(200,168,120,0.08); border-radius: 18px; padding: 14px; backdrop-filter: blur(8px); }
.fantasy-card-title { font-size: 12px; font-weight: 700; color: #c8a878; font-family: 'Space Mono', monospace; margin-bottom: 10px; letter-spacing: 0.04em; }
.fantasy-stats { display: flex; gap: 16px; font-size: 13px; font-weight: 700; color: #e8d8b8; }
.fantasy-hp-bars { display: grid; gap: 6px; margin-top: 8px; }
.fantasy-bar-row { display: flex; align-items: center; gap: 8px; font-size: 11px; color: rgba(200,168,120,0.6); }
.bar { flex: 1; height: 6px; border-radius: 999px; background: rgba(255,255,255,0.04); overflow: hidden; }
.bar-fill { height: 100%; border-radius: 999px; transition: width 300ms ease; }
.bar-red { background: #ef4444; }
.bar-blue { background: #3b82f6; }

.fantasy-unit-detail { display: grid; gap: 4px; }
.fantasy-unit-detail div { display: flex; justify-content: space-between; font-size: 12px; color: rgba(200,168,120,0.7); }
.fantasy-unit-detail strong { color: #e8d8b8; }

.fantasy-battle-log { margin-top: 8px; display: grid; gap: 2px; }
.fantasy-log-line { font-size: 10px; color: rgba(200,168,120,0.5); font-family: 'Space Mono', monospace; overflow-wrap: anywhere; padding-left: 6px; border-left: 2px solid transparent; margin-bottom: 2px; }
.log-attack { color: #ef4444; border-left-color: rgba(239,68,68,0.3); }
.log-heal { color: #4ade80; border-left-color: rgba(74,222,128,0.3); }
.log-result { color: #fbbf24; font-weight: 800; border-left-color: rgba(251,191,36,0.3); }
.log-danger { color: #f97316; border-left-color: rgba(249,115,22,0.3); animation: log-flash 1s ease-in-out infinite; }
.log-lb { color: #a855f7; font-weight: 800; border-left-color: rgba(168,85,247,0.3); }
@keyframes log-flash { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }
.fantasy-battle-status { font-size: 11px; color: #4ade80; text-align: center; font-family: 'Space Mono', monospace; }
.fantasy-result { font-size: 24px; font-weight: 900; color: #fbbf24; text-align: center; font-family: 'Space Mono', monospace; margin: 8px 0; }
.fantasy-mvp { font-size: 11px; color: #c8a878; text-align: center; font-family: 'Space Mono', monospace; }
.stat-section { margin-bottom: 8px; }
.stat-section:last-child { margin-bottom: 0; }
.stat-section-label { font-size: 8px; font-weight: 700; color: rgba(200,168,120,0.35); font-family: 'Space Mono', monospace; letter-spacing: 0.08em; margin-bottom: 3px; text-transform: uppercase; }
.stat-row { display: flex; align-items: center; gap: 4px; padding: 2px 0; font-size: 9px; font-family: 'Space Mono', monospace; transition: opacity 300ms; }
.stat-row.dead { opacity: 0.25; }
.stat-icon { font-size: 10px; width: 14px; text-align: center; }
.stat-name { color: rgba(200,168,120,0.5); min-width: 40px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stat-team { font-size: 7px; }
.stat-bar { flex: 1; height: 6px; border-radius: 3px; background: rgba(255,255,255,0.03); overflow: hidden; min-width: 30px; }
.stat-bar-fill { height: 100%; border-radius: 3px; transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); }
.bar-dps { background: linear-gradient(90deg, #ef4444, #f97316); }
.bar-hps { background: linear-gradient(90deg, #4ade80, #22c55e); }
.bar-taken { background: linear-gradient(90deg, #3b82f6, #6366f1); }
.stat-val { color: rgba(200,168,120,0.6); min-width: 30px; text-align: right; font-variant-numeric: tabular-nums; font-size: 8px; }
.lb-row { display: flex; align-items: center; gap: 6px; font-size: 11px; font-family: 'Space Mono', monospace; margin-bottom: 4px; }
.lb-label { font-size: 10px; }
.lb-track { flex: 1; height: 8px; border-radius: 4px; background: rgba(255,255,255,0.04); overflow: hidden; }
.lb-fill { height: 100%; border-radius: 4px; transition: width 0.3s ease; }
.lb-fill.lb-red { background: linear-gradient(90deg, #ef4444, #fbbf24); box-shadow: 0 0 8px rgba(239,68,68,0.3); }
.lb-fill.lb-blue { background: linear-gradient(90deg, #3b82f6, #a855f7); box-shadow: 0 0 8px rgba(59,130,246,0.3); }
.lb-val { color: rgba(200,168,120,0.5); font-variant-numeric: tabular-nums; font-size: 10px; }
.fantasy-speed-control { display: flex; align-items: center; gap: 8px; }
.speed-label { font-size: 10px; color: rgba(200,168,120,0.4); font-family: 'Space Mono', monospace; }
.speed-btns { display: flex; gap: 3px; }
.speed-btns button { padding: 4px 10px; border-radius: 999px; border: 1px solid rgba(200,168,120,0.1); background: transparent; color: rgba(200,168,120,0.4); font-size: 10px; font-family: 'Space Mono', monospace; cursor: pointer; transition: all 120ms; }
.speed-btns button.active { background: rgba(200,168,120,0.15); color: #c8a878; border-color: rgba(200,168,120,0.2); }

@media (max-width: 1100px) {
  .fantasy-topbar {
    align-items: flex-start;
    flex-direction: column;
  }
  .fantasy-actions {
    justify-content: flex-start;
  }
  .fantasy-console {
    grid-template-columns: 1fr;
    height: auto;
  }
  .fantasy-main {
    min-height: min(62vh, 620px);
  }
  .fantasy-side {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow: visible;
    max-height: none;
    padding-right: 0;
  }
}

@media (max-width: 720px) {
  .fantasy-page {
    min-height: 100vh;
    padding: 14px;
  }
  .fantasy-eye {
    letter-spacing: 0.18em;
  }
  .fantasy-topbar h1 {
    font-size: clamp(30px, 11vw, 42px);
    line-height: 1;
  }
  .fantasy-actions,
  .fantasy-btn,
  .fantasy-actions-vertical {
    width: 100%;
  }
  .fantasy-console {
    gap: 14px;
  }
  .fantasy-main {
    min-height: 420px;
  }
  .fantasy-side {
    grid-template-columns: 1fr;
  }
  .fantasy-stats,
  .fantasy-speed-control {
    flex-wrap: wrap;
  }
}
</style>
