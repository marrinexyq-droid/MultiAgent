# Multi-Agent Tactical Simulation Platform

A hex-grid based multi-agent tactical combat simulation platform with real-time visualization, replay, and statistics.

## Features

### Combat Engine
- **Hex Grid System** — distance, pathfinding, line-of-sight (LOS), AoE range calculation on axial coordinates
- **8 Terrain Types** — OPEN / ROAD / FOREST / URBAN / WATER / ROUGH / MARSH / MOUNTAIN — each with distinct MP cost, cover bonus, concealment, and LOS blocking
- **Turn-based Combat** — move, attack, skill usage, buff/debuff, damage/heal resolution
- **War Fog** — per-team visibility grid with explored/unexplored states, terrain LOS blocking
- **LB (Limit Break)** — team-shared gauge (+3/turn base, +1 per 200 damage taken)

### Agent Decision
- **Hybrid LLM+Rule AI** — agents use LLM (OpenAI-compatible) when API available, fall back to role-specific rule-based strategies
- **Shared Memory Pool** — probabilistic confidence-based belief system with multi-source cross-validation, role-weighted source trust, and turn-by-turn decay
- **6 Agent Roles** — Commander, Scout, Attacker, Defender, Support, Controller — each with distinct read context and decision logic

### Visualization
- **SVG Hex Rendering** — 3D bevel effect with diagonal lighting (military sci-fi theme)
- **Fantasy Mode** — FF14-inspired 8-player party combat with 40+ skills, combos, jobs
- **Battle Replay** — frame-by-frame comparison, diff overlay, auto-pause on key events
- **Damage Numbers** — floating damage/heal/crit indicators with CSS animations
- **Cast Bars** — unit overhead casting progress bar
- **DPS/HPS Charts** — real-time bar charts with elastic transition
- **Interactive Map** — hover tooltips, buff icons, death markers, AoE danger zones

### Statistics & Analysis
- Cumulative damage dealt / taken / healing per unit
- DPS / HPS / damage taken real-time stats
- MVP calculation on battle settlement
- Color-coded battle log (red=attack, green=heal, gold=result)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 + TypeScript + Vite |
| Backend | Python + FastAPI |
| AI | OpenAI-compatible API (SiliconFlow) + rule-based fallback |
| Deployment | Single binary via FastAPI + static frontend |

## Quick Start

### Backend

```bash
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn
python -m src.battle.api_server
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in browser.

### Fantasy Mode

After starting the API server, navigate to `/fantasy` route. The fantasy battle uses the same backend with a separate agent set and 8-player party format.

## Project Structure

```
src/
├── battle/
│   ├── env.py                # Base battlefield environment
│   ├── ff14_env.py           # Fantasy battle engine (8v8, 40+ skills)
│   ├── grid_rules.py         # Hex grid math (distance, LOS, neighbors)
│   ├── terrain.py            # Terrain properties and generators
│   ├── battle_types.py       # Shared data models
│   ├── stats.py              # Statistics tracking
│   ├── memory.py             # Shared memory pool (belief + decay)
│   ├── fantasy_api.py        # Fantasy mode FastAPI router
│   ├── api_server.py         # Main FastAPI server
│   ├── ff14_skills.py        # Skill definitions + combo chains
│   └── ff14_roster.py        # Job templates (8 roles)
├── agents/
│   ├── ff14_agent.py         # Fantasy hybrid LLM+Rule agent
│   ├── generic.py            # Rule-based tactical agent
│   ├── red/                  # Red team agent implementations
│   └── blue/                 # Blue team agent implementations
frontend/
├── src/
│   ├── components/
│   │   ├── FantasyMap.vue    # Fantasy hex map with unit badges & effects
│   │   ├── HexBattleMap.vue  # Military hex map with 3D terrain & fog
│   │   ├── HexDamageNumber.vue # Floating damage indicators
│   │   └── ...
│   ├── views/
│   │   ├── FantasyPage.vue   # Fantasy battle main page
│   │   ├── HexLabPage.vue    # Military simulation main page
│   │   └── ...
│   └── styles.css            # Global styles (dark theme)
```

## Architecture

```
Agent (LLM/Rule) → Env (hex grid + combat) → Events → Stats → Frontend (Vue 3)
       ↓
  SharedMemoryPool (beliefs + decay + role-based context)
```

The system is a **multi-agent tactical simulation sandbox**: agents make decisions based on battlefield state, the environment resolves actions and generates structured events, and the frontend renders a frame-by-frame replay with full statistics.

## License

MIT
