<template>
  <section class="fantasy-map-card">
    <div class="fantasy-map-head">
      <div class="fantasy-hud">FANTASY BATTLE v1.0</div>
      <div class="fantasy-round">ROUND {{ turn }}</div>
    </div>

    <div v-if="frame" class="fantasy-board-scroll" ref="boardRef" @wheel.prevent>
      <div class="fantasy-board" :style="boardStyle">
        <div v-for="(cell, i) in cells" :key="i" class="fantasy-cell" :class="cell.classes" :style="cell.style" @click="onCellClick(cell)" @mouseenter="hovered = cell" @mouseleave="hovered = null">
          <svg class="fantasy-cell-bg" viewBox="0 0 78 88" aria-hidden="true">
            <polygon points="39,0 77,22 77,66 39,88 1,66 1,22" :fill="cell.color" />
            <polygon points="39,0 77,22 39,44 1,22" fill="rgba(255,255,255,0.1)" />
            <polygon points="39,44 77,66 39,88 1,66" fill="rgba(0,0,0,0.08)" />
            <line x1="1" y1="22" x2="39" y2="0" stroke="rgba(255,255,255,0.15)" stroke-width="2" />
            <line x1="39" y1="0" x2="77" y2="22" stroke="rgba(255,255,255,0.1)" stroke-width="1.5" />
            <line x1="1" y1="66" x2="39" y2="88" stroke="rgba(0,0,0,0.15)" stroke-width="2" />
            <line x1="39" y1="88" x2="77" y2="66" stroke="rgba(0,0,0,0.1)" stroke-width="1.5" />
          </svg>

          <!-- AOE danger preview -->
          <div v-if="cell.inAoe" class="fantasy-aoe-preview"></div>
          <div v-if="cell.inHeal" class="fantasy-heal-preview"></div>
          <div v-if="cell.inAtkRange" class="fantasy-range-overlay"></div>

          <!-- Unit badge -->
          <div v-if="cell.unit" class="fantasy-unit" :class="[`team-${cell.unit.team}`, { dead: !cell.unit.alive }]">
            <div class="fantasy-unit-icon">{{ cell.unit.icon }}</div>
            <div class="fantasy-unit-group">{{ cell.unit.group.toUpperCase() }}</div>
            <div class="fantasy-unit-hp"><div class="fantasy-hp-fill" :style="{ width: (cell.unit.hp / cell.unit.max_hp * 100) + '%', background: hpColor(cell.unit.hp, cell.unit.max_hp) }"></div></div>
            <div class="fantasy-unit-hp-text">{{ formatNum(cell.unit.hp) }}</div>
            <div v-if="hasBuffs(cell.unit)" class="fantasy-unit-buffs">{{ formatBuffs(cell.unit.buffs) }}</div>
          </div>

          <!-- Cast bar on unit -->
          <div v-if="cell.castBar" class="fantasy-cast-bar-unit" :class="`cast-${cell.castBar.team}`">
            <div class="fantasy-cast-bar-label">{{ cell.castBar.name }}</div>
            <div class="fantasy-cast-bar-track"><div class="fantasy-cast-bar-fill" :style="{ width: cell.castBar.pct + '%' }"></div></div>
          </div>
        </div>

        <!-- Damage numbers layer -->
        <div class="fantasy-dmg-layer">
          <div v-for="d in dmgNumbers" :key="d.key" class="fantasy-dmg" :class="`dmg-${d.type}`" :style="{ left: d.x + 'px', top: d.y + 'px' }">{{ d.text }}</div>
        </div>

        <!-- Skill effects SVG -->
        <svg class="fantasy-fx-layer" :width="boardWidth" :height="boardHeight">
          <g v-for="fx in skillFX" :key="fx.key">
            <circle v-if="fx.l1" :cx="fx.cx" :cy="fx.cy" :r="fx.r" :class="`fx fx-${fx.type} fx-l1`" :style="fx.style" />
            <circle v-if="fx.l2" :cx="fx.cx" :cy="fx.cy" :r="fx.r * 0.6" :class="`fx fx-${fx.type} fx-l2`" />
            <line v-if="fx.l3" :x1="fx.cx - 10" :y1="fx.cy - 10" :x2="fx.cx + 10" :y2="fx.cy + 10" :class="`fx-slash`" />
            <line v-if="fx.l3" :x1="fx.cx + 10" :y1="fx.cy - 10" :x2="fx.cx - 10" :y2="fx.cy + 10" :class="`fx-slash`" />
          </g>
          <line v-for="b in beamFX" :key="b.key" :x1="b.x1" :y1="b.y1" :x2="b.x2" :y2="b.y2" :class="`fx-beam beam-${b.type}`" />
        </svg>

        <!-- AoE Danger Zones -->
        <div v-for="dz in dangerZones" :key="dz.key" class="fantasy-danger-zone" :style="dz.style">
          <div class="fantasy-danger-inner">⚠</div>
        </div>
        <div class="fantasy-particles"><div v-for="p in particles" :key="p.id" class="fantasy-particle" :style="p.style"></div></div>
      </div>
    </div>
            <div v-if="hovered?.unit" class="fantasy-tooltip" :style="tooltipStyle">
              <strong>{{ hovered.unit.icon }} {{ hovered.unit.role_label }}</strong>
              <span>HP {{ formatNum(hovered.unit.hp) }}/{{ formatNum(hovered.unit.max_hp) }}</span>
              <span v-if="hovered.unit.group === 'healer'">HPS {{ hoveredHPS }}</span>
              <span v-else-if="hovered.unit.group !== 'dps'">DPS {{ hoveredDPS }}</span>
              <span v-if="hasBuffs(hovered.unit)">Buff: {{ formatBuffs(hovered.unit.buffs) }}</span>
            </div>
            <div v-else class="fantasy-empty">✨ 点击创建魔幻演练 ✨</div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

const props = defineProps<{ frame: any; turn: number; focusedId?: string; castBars?: Array<{ agentId: string; skillName: string; pct: number }> }>();
const emit = defineEmits<{ "cell-click": [cell: any] }>();

const hexW = 78, hexH = 88, rowStep = hexH * 0.75, pad = 34;

const TERRAIN_COLORS: Record<string, string> = {
  open: "#c8b898", road: "#d4c8a8", forest: "#6ab86a",
  urban: "#b89878", water: "#68b8d8", rough: "#b8a878",
  marsh: "#8ab888", mountain: "#b8a088",
};

function hpColor(hp: number, maxHp: number): string {
  const pct = hp / maxHp;
  if (pct > 0.6) return "linear-gradient(90deg, #4ade80, #22c55e)";
  if (pct > 0.3) return "linear-gradient(90deg, #fbbf24, #f59e0b)";
  return "linear-gradient(90deg, #ef4444, #dc2626)";
}
const BUFF_ICONS: Record<string, string> = {
  defense_up: "🛡", damage_up: "⚔", crit_up: "🎯", shield: "🔵",
  party_shield: "🔷", regen: "💚", thorns: "🔴", party_defense: "🔰",
  party_attack: "📈", party_burst: "💥", undying: "♾", bleed: "🩸",
  slow: "🐢", vulnerability: "🔻", poison: "☠", cc_immune: "🛡",
  pet: "✨",
};
function hasBuffs(unit: any): boolean {
  return unit.buffs && typeof unit.buffs === "object" && Object.keys(unit.buffs).length > 0;
}
function formatBuffs(buffs: Record<string, number>): string {
  return Object.entries(buffs).map(([k, v]) => `${BUFF_ICONS[k] || "?"}`).join("");
}
function formatNum(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + "w";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}
function hexDist(a: any, b: any): number {
  const aq = a.x - Math.floor((a.y - (a.y & 1)) / 2);
  const bq = b.x - Math.floor((b.y - (b.y & 1)) / 2);
  return (Math.abs(aq - bq) + Math.abs(aq + a.y - bq - b.y) + Math.abs(a.y - b.y)) / 2;
}
function cellCx(x: number, y: number): number { return pad + x * hexW + (y % 2 ? hexW / 2 : 0) + hexW / 2; }
function cellCy(x: number, y: number): number { return pad + y * rowStep + hexH / 2; }
function getTerrain(x: number, y: number): string { return props.frame?.map.terrain?.[y]?.[x]?.type ?? "open"; }

const boardWidth = computed(() => { const w = props.frame?.map.width ?? 12; return pad * 2 + w * hexW + hexW / 2; });
const boardHeight = computed(() => { const h = props.frame?.map.height ?? 10; return pad * 2 + Math.max(1, h) * rowStep + hexH - rowStep; });
const boardStyle = computed(() => ({ width: `${boardWidth.value}px`, height: `${boardHeight.value}px` }));

/* ── Cells with range & cast bars ── */
const cells = computed(() => {
  const f = props.frame;
  if (!f) return [];
  const r: any[] = [];

  const atkCells = new Set<string>();
  let lastAoeTarget: any = null, aoeRadius = 0;
  let lastHealTarget: any = null;
  if (props.focusedId) {
    const fu = f.units?.find((u: any) => u.agent_id === props.focusedId);
    if (fu?.alive) {
      const range = fu.attack_range || 1;
      for (let ay = 0; ay < f.map.height; ay++) {
        for (let ax = 0; ax < f.map.width; ax++) {
          if (hexDist(fu.pos, { x: ax, y: ay }) <= range) atkCells.add(`${ax},${ay}`);
        }
      }
    }
  }

  /* Simulated cast bars from events */
  const castMap: Record<string, { name: string; pct: number; team: string }> = {};
  if (props.castBars?.length) {
    for (const cb of props.castBars) {
      const unit = f.units?.find((u: any) => u.agent_id === cb.agentId);
      if (unit) castMap[cb.agentId] = { name: cb.skillName, pct: cb.pct, team: unit.team };
    }
  }

  for (let y = 0; y < f.map.height; y++) {
    for (let x = 0; x < f.map.width; x++) {
      const unit = f.units?.find((u: any) => u.pos.x === x && u.pos.y === y) ?? null;
      const tt = getTerrain(x, y);
      const key = `${x},${y}`;
      r.push({
        x, y, unit,
        color: TERRAIN_COLORS[tt] ?? "#c8b898",
        inAtkRange: atkCells.has(key) && !unit,
        inAoe: false, inHeal: false,
        castBar: unit ? castMap[unit.agent_id] || null : null,
        classes: { "fantasy-range-cell": atkCells.has(key) && !unit },
        style: { left: `${pad + x * hexW + (y % 2 ? hexW / 2 : 0)}px`, top: `${pad + y * rowStep}px` },
      });
    }
  }
  return r;
});

/* ── Enhanced skill effects ── */
const skillFX = computed(() => {
  const f = props.frame;
  if (!f?.events_structured) return [];
  const circles: any[] = [];
  for (const ev of f.events_structured) {
    const meta = ev.metadata || {};
    const effect = meta.effect || "attack";
    const pos = ev.target_position || {};
    if (pos.x === undefined || pos.y === undefined) continue;
    const cx = cellCx(pos.x, pos.y), cy = cellCy(pos.x, pos.y);
    const base: any = { key: `fx-${ev.turn}-${ev.actor_id}`, cx, cy, type: effect };

    if (effect === "attack") {
      base.r = 18; base.l1 = true; base.l2 = true; base.l3 = true;
      base.style = { animationDuration: "0.5s" };
    } else if (effect === "big_attack") {
      base.r = 28; base.l1 = true; base.l2 = true; base.l3 = true;
      base.style = { animationDuration: "0.6s" };
    } else if (effect === "heal") {
      base.r = 22; base.l1 = true; base.l2 = true; base.l3 = false;
      base.style = { animationDuration: "0.7s" };
    } else if (effect === "shield") {
      base.r = 24; base.l1 = true; base.l2 = false; base.l3 = false;
      base.style = { animationDuration: "1s" };
    } else if (effect === "aoe") {
      base.r = 32; base.l1 = true; base.l2 = true; base.l3 = false;
      base.style = { animationDuration: "0.8s" };
    } else if (effect === "ultimate") {
      base.r = 40; base.l1 = true; base.l2 = true; base.l3 = false;
      base.style = { animationDuration: "1.2s" };
    } else if (effect === "defense") {
      base.r = 16; base.l1 = true; base.l2 = true; base.l3 = false;
      base.style = { animationDuration: "0.6s" };
    } else if (effect === "buff") {
      base.r = 14; base.l1 = true; base.l2 = false; base.l3 = false;
      base.style = { animationDuration: "0.5s" };
    } else {
      base.r = 18; base.l1 = true; base.l2 = false; base.l3 = false;
      base.style = {};
    }
    circles.push(base);
  }
  return circles;
});

const beamFX = computed(() => {
  const f = props.frame;
  if (!f?.events_structured) return [];
  const beams: any[] = [];
  for (const ev of f.events_structured) {
    const effect = (ev.metadata || {}).effect || "";
    if (!ev.actor_id || !ev.target_position || !["heal", "shield", "attack"].includes(effect)) continue;
    const actor = f.units?.find((u: any) => u.agent_id === ev.actor_id);
    if (!actor) continue;
    const t = ev.target_position;
    beams.push({ key: `beam-${ev.turn}`, x1: cellCx(actor.pos.x, actor.pos.y), y1: cellCy(actor.pos.x, actor.pos.y), x2: cellCx(t.x, t.y), y2: cellCy(t.x, t.y), type: effect });
  }
  return beams;
});

/* ── Cumulative damage/heal numbers from unit totals ── */
const dmgNumbers = computed(() => {
  const f = props.frame;
  if (!f?.units) return [];
  const items: any[] = [];
  for (const u of f.units) {
    const cx = cellCx(u.pos.x, u.pos.y), cy = cellCy(u.pos.x, u.pos.y) - 20;
    if (u.total_damage_dealt > 0) items.push({ key: `dmg-${u.agent_id}`, x: cx, y: cy, text: `-${u.total_damage_dealt}`, type: u.alive ? "normal" : "dead" });
    if (u.total_healing_done > 0) items.push({ key: `heal-${u.agent_id}`, x: cx, y: cy, text: `+${u.total_healing_done}`, type: "heal" });
  }
  return items;
});

function onCellClick(c: any) { emit("cell-click", c); }

const hovered = ref<any>(null);
const tooltipStyle = computed(() => {
  if (!hovered.value?.unit) return {};
  const unit = hovered.value.unit;
  const cx = cellCx(unit.pos.x, unit.pos.y);
  const cy = cellCy(unit.pos.x, unit.pos.y);
  return { left: `${cx}px`, top: `${cy - 50}px` };
});
const hoveredDPS = computed(() => {
  const u = hovered.value?.unit;
  if (!u || !props.frame?.stats) return 0;
  const s = props.frame.stats.find((st: any) => st.agent_id === u.agent_id);
  return s?.dps ?? 0;
});
const hoveredHPS = computed(() => {
  const u = hovered.value?.unit;
  if (!u || !props.frame?.stats) return 0;
  const s = props.frame.stats.find((st: any) => st.agent_id === u.agent_id);
  return s?.hps ?? 0;
});

const dangerZones = computed(() => {
  const f = props.frame;
  if (!f?.danger_zones) return [];
  return f.danger_zones.map((dz: any, i: number) => {
    const cx = cellCx(dz.center.x, dz.center.y);
    const cy = cellCy(dz.center.x, dz.center.y);
    const size = (dz.radius || 1) * hexW * 1.5;
    return {
      key: `dz-${i}`,
      style: { left: `${cx - size / 2}px`, top: `${cy - size / 2}px`, width: `${size}px`, height: `${size}px` },
    };
  });
});

const particles = ref<Array<{ id: number; style: Record<string, string> }>>([]);
onMounted(() => {
  const items = [];
  for (let i = 0; i < 20; i++) {
    const s = 2 + Math.random() * 4;
    items.push({ id: i, style: { left: `${Math.random() * 100}%`, top: `${Math.random() * 100}%`, width: `${s}px`, height: `${s}px`, animationDelay: `${Math.random() * 5}s`, animationDuration: `${3 + Math.random() * 4}s`, opacity: 0.2 + Math.random() * 0.3 } });
  }
  particles.value = items;
});
</script>

<style scoped>
.fantasy-map-card { min-height: 600px; border-radius: 24px; background: linear-gradient(145deg, #1a0a2e, #2a1a4a); border: 1px solid rgba(200,168,120,0.15); box-shadow: 0 8px 40px rgba(0,0,0,0.4), inset 0 0 60px rgba(100,80,180,0.05); overflow: hidden; position: relative; }
.fantasy-map-head { display: flex; justify-content: space-between; align-items: center; padding: 10px 16px; background: rgba(200,168,120,0.05); border-bottom: 1px solid rgba(200,168,120,0.1); }
.fantasy-hud { font-size: 11px; font-weight: 700; color: #c8a878; letter-spacing: 0.12em; font-family: 'Space Mono', monospace; }
.fantasy-round { padding: 4px 12px; border-radius: 999px; background: rgba(200,168,120,0.1); color: #e8d8b8; font-size: 11px; font-weight: 800; font-family: 'Space Mono', monospace; border: 1px solid rgba(200,168,120,0.15); }
.fantasy-board-scroll { height: min(65vh, 700px); overflow: auto; background: radial-gradient(ellipse at 50% 30%, #2a1a4a 0%, #1a0a2e 70%); position: relative; }
.fantasy-board { position: relative; margin: 24px auto; }
.fantasy-cell { position: absolute; width: 78px; height: 88px; clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%); cursor: pointer; transition: transform 150ms ease, filter 150ms ease; overflow: visible; }
.fantasy-cell:hover { z-index: 10; filter: brightness(1.15); transform: scale(1.03); }
.fantasy-cell-bg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; display: block; filter: drop-shadow(0 0 6px rgba(200,168,120,0.06)); }
.fantasy-unit { position: absolute; z-index: 5; left: 50%; top: 50%; transform: translate(-50%, -50%); display: grid; place-items: center; gap: 1px; pointer-events: none; }
.fantasy-unit-icon { font-size: 22px; filter: drop-shadow(0 0 8px rgba(255,255,255,0.3)); }
.fantasy-unit-group { font-size: 8px; font-weight: 800; color: rgba(255,255,255,0.6); font-family: 'Space Mono', monospace; letter-spacing: 0.1em; background: rgba(0,0,0,0.3); padding: 1px 6px; border-radius: 4px; }
.fantasy-unit-hp { width: 36px; height: 3px; border-radius: 2px; background: rgba(0,0,0,0.4); overflow: hidden; }
.fantasy-hp-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #4ade80, #22c55e); transition: width 300ms ease; }
.fantasy-unit-hp-text { font-size: 7px; font-weight: 700; color: rgba(255,255,255,0.5); font-family: 'Space Mono', monospace; font-variant-numeric: tabular-nums; position: absolute; bottom: -10px; }
.fantasy-unit-buffs { position: absolute; top: -8px; left: 50%; transform: translateX(-50%); display: flex; gap: 1px; font-size: 8px; line-height: 1; pointer-events: none; filter: drop-shadow(0 0 3px rgba(0,0,0,0.5)); }
.fantasy-unit.team-red .fantasy-unit-icon { filter: drop-shadow(0 0 10px rgba(239,68,68,0.4)); }
.fantasy-unit.team-blue .fantasy-unit-icon { filter: drop-shadow(0 0 10px rgba(59,130,246,0.4)); }
.fantasy-unit.dead { opacity: 0.15; filter: grayscale(1) brightness(0.4); pointer-events: none; transition: all 0.8s ease; }
.fantasy-unit.dead .fantasy-unit-icon::after { content: '✕'; position: absolute; top: -6px; right: -8px; font-size: 16px; color: rgba(239,68,68,0.5); font-weight: 900; }
.fantasy-tooltip { position: absolute; z-index: 30; background: rgba(15,10,25,0.9); border: 1px solid rgba(200,168,120,0.15); border-radius: 8px; padding: 6px 10px; pointer-events: none; transform: translateX(-50%); display: grid; gap: 2px; }
.fantasy-tooltip strong { font-size: 11px; color: #c8a878; font-family: 'Space Mono', monospace; }
.fantasy-tooltip span { font-size: 9px; color: rgba(200,168,120,0.6); font-family: 'Space Mono', monospace; }
.fantasy-danger-zone { position: absolute; z-index: 6; pointer-events: none; border-radius: 50%; background: rgba(239,68,68,0.08); border: 2px dashed rgba(239,68,68,0.35); animation: dz-flash 0.6s ease-in-out infinite; display: grid; place-items: center; }
.fantasy-danger-inner { font-size: 20px; color: rgba(239,68,68,0.4); animation: dz-pulse 0.4s ease-in-out infinite alternate; }
@keyframes dz-flash { 0%, 100% { opacity: 0.5; } 50% { opacity: 1; } }
@keyframes dz-pulse { 0% { transform: scale(0.8); } 100% { transform: scale(1.1); } }

/* Range */ 
.fantasy-range-cell { z-index: 2; }
.fantasy-range-overlay { position: absolute; inset: 0; background: rgba(200,168,120,0.06); border: 1px solid rgba(200,168,120,0.12); pointer-events: none; animation: range-pulse 1.5s ease-in-out infinite; }
@keyframes range-pulse { 0%, 100% { opacity: 0.2; } 50% { opacity: 0.5; } }

/* AOE danger preview */
.fantasy-aoe-preview { position: absolute; inset: 0; background: rgba(239,68,68,0.06); border: 2px dashed rgba(239,68,68,0.2); pointer-events: none; animation: aoe-flash 0.8s ease-in-out infinite; }
@keyframes aoe-flash { 0%, 100% { opacity: 0.3; } 50% { opacity: 0.7; } }
.fantasy-heal-preview { position: absolute; inset: 0; background: rgba(74,222,128,0.06); border: 2px dashed rgba(74,222,128,0.2); pointer-events: none; animation: aoe-flash 1s ease-in-out infinite; }

/* Cast bar on unit */
.fantasy-cast-bar-unit { position: absolute; z-index: 8; bottom: 4px; left: 50%; transform: translateX(-50%); width: 48px; height: 14px; }
.fantasy-cast-bar-label { font-size: 6px; font-weight: 800; color: #e8d8b8; text-align: center; letter-spacing: 0.04em; margin-bottom: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fantasy-cast-bar-track { width: 100%; height: 3px; border-radius: 2px; background: rgba(0,0,0,0.4); overflow: hidden; }
.fantasy-cast-bar-fill { height: 100%; border-radius: 2px; transition: width 100ms linear; }
.cast-red .fantasy-cast-bar-fill { background: #ef4444; }
.cast-blue .fantasy-cast-bar-fill { background: #3b82f6; }

/* Damage numbers */
.fantasy-dmg-layer { position: absolute; inset: 0; pointer-events: none; overflow: visible; z-index: 20; }
.fantasy-dmg { position: absolute; font-family: 'Space Mono', monospace; font-weight: 900; pointer-events: none; transform: translate(-50%, -50%); animation: dmg-float 1.2s ease-out forwards; font-variant-numeric: tabular-nums; }
.fantasy-dmg.dmg-normal { font-size: 24px; color: #ef4444; text-shadow: 0 0 12px rgba(239,68,68,0.4), 0 2px 4px rgba(0,0,0,0.5); }
.fantasy-dmg.dmg-crit { font-size: 36px; color: #fbbf24; text-shadow: 0 0 20px rgba(251,191,36,0.5), 0 2px 4px rgba(0,0,0,0.5); }
.fantasy-dmg.dmg-heal { font-size: 28px; color: #4ade80; text-shadow: 0 0 16px rgba(74,222,128,0.4), 0 2px 4px rgba(0,0,0,0.5); }
.fantasy-dmg.dmg-dead { font-size: 20px; color: rgba(239,68,68,0.3); text-shadow: none; }
@keyframes dmg-float { 0% { opacity: 1; transform: translate(-50%, 0); } 50% { opacity: 1; } 100% { opacity: 0; transform: translate(-50%, -40px); } }

/* Skill effects */
.fantasy-fx-layer { position: absolute; inset: 0; pointer-events: none; overflow: visible; z-index: 3; }
.fx { fill: none; stroke-width: 3; }
.fx-l1 { animation: fx-expand 0.6s ease-out forwards; }
.fx-l2 { stroke-width: 2; opacity: 0.6; animation: fx-expand 0.8s ease-out forwards 0.1s; }

.fx-attack { stroke: #ef4444; filter: drop-shadow(0 0 8px rgba(239,68,68,0.5)); }
.fx-big_attack { stroke: #ef4444; stroke-width: 5; filter: drop-shadow(0 0 12px rgba(239,68,68,0.6)); }
.fx-heal { stroke: #4ade80; filter: drop-shadow(0 0 10px rgba(74,222,128,0.5)); }
.fx-shield { stroke: #3b82f6; stroke-dasharray: 8 6; filter: drop-shadow(0 0 8px rgba(59,130,246,0.4)); animation: fx-rotate 1.2s linear forwards; }
.fx-defense { stroke: #fbbf24; filter: drop-shadow(0 0 8px rgba(251,191,36,0.4)); }
.fx-buff { stroke: #f59e0b; stroke-dasharray: 6 8; filter: drop-shadow(0 0 6px rgba(245,158,11,0.4)); }
.fx-regen { stroke: #22c55e; stroke-dasharray: 10 5; }
.fx-aoe { stroke: #f97316; stroke-width: 4; filter: drop-shadow(0 0 12px rgba(249,115,22,0.5)); }
.fx-ultimate { stroke: #a855f7; stroke-width: 5; filter: drop-shadow(0 0 20px rgba(168,85,247,0.6)); animation: fx-expand-ult 1.2s ease-out forwards; }

.fx-slash { stroke: rgba(255,255,255,0.6); stroke-width: 2; stroke-linecap: round; animation: fx-slash 0.3s ease-out forwards; filter: drop-shadow(0 0 6px rgba(255,255,255,0.3)); }
@keyframes fx-slash { 0% { opacity: 1; } 100% { opacity: 0; } }
@keyframes fx-expand { 0% { opacity: 1; } 100% { opacity: 0; } }
@keyframes fx-expand-ult { 0% { opacity: 1; r: 20; } 30% { opacity: 1; r: 40; } 100% { opacity: 0; r: 60; } }
@keyframes fx-rotate { 0% { transform: rotate(0deg); opacity: 1; } 100% { transform: rotate(360deg); opacity: 0; } }

.fx-beam { stroke-width: 3; stroke-linecap: round; fill: none; animation: beam-last 0.6s ease-out forwards; }
.beam-heal { stroke: #4ade80; filter: drop-shadow(0 0 10px rgba(74,222,128,0.4)); }
.beam-shield { stroke: #3b82f6; filter: drop-shadow(0 0 10px rgba(59,130,246,0.4)); stroke-dasharray: 6 8; }
.beam-attack { stroke: #ef4444; filter: drop-shadow(0 0 8px rgba(239,68,68,0.4)); stroke-dasharray: 4 8; }
@keyframes beam-last { 0% { opacity: 0.8; } 100% { opacity: 0; } }

.fantasy-particles { position: absolute; inset: 0; pointer-events: none; overflow: hidden; z-index: 1; }
.fantasy-particle { position: absolute; border-radius: 50%; background: rgba(255,255,255,0.25); animation: float-up linear infinite; box-shadow: 0 0 4px rgba(200,168,120,0.2); }
@keyframes float-up { 0% { transform: translateY(100%) scale(0.5); opacity: 0; } 20% { opacity: 0.6; } 80% { opacity: 0.6; } 100% { transform: translateY(-100vh) scale(1); opacity: 0; } }
.fantasy-empty { padding: 60px; text-align: center; color: rgba(200,168,120,0.3); font-size: 16px; }
</style>
