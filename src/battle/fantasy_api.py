from fastapi import APIRouter, HTTPException

from .battle_types import Action, ActionType, Position, Team, TacticalEvent
from .ff14_env import FantasyEnv
from .ff14_skills import SKILLS
from .agents.ff14_agent import Ff14Agent, build_obs

router = APIRouter(prefix="/api/fantasy")
sessions: dict[str, dict] = {}


# Frontline jobs: dark_knight, warrior (tanks), dragoon, monk (melee)
# Backline jobs: black_mage, bard (ranged dps), white_mage, scholar (healers)
FRONTLINE = {"dark_knight", "warrior", "dragoon", "monk"}
BACKLINE = {"black_mage", "bard", "white_mage", "scholar"}


def spawn_positions(team_side: int, width: int, height: int) -> dict[str, list[Position]]:
    """Both teams: front=column team_side (facing center), back=column team_side+2"""
    front, back = [], []
    for y in range(height):
        front.append(Position(team_side, y))
        back.append(Position(min(team_side + 2, width - 1), y))
    return {"front": front, "back": back}


def compute_stats(env: FantasyEnv) -> dict:
    """Compute DPS/HPS/承伤 from accumulated unit totals."""
    turn = max(1, env.turn)
    stats = []
    for uid in env.units:
        u = env.units[uid]
        stats.append({
            "agent_id": uid, "role_label": u.job.label, "icon": u.job.icon,
            "team": u.team.value, "alive": u.alive,
            "dps": round(u.total_damage_dealt / turn, 1),
            "hps": round(u.total_healing_done / turn, 1),
            "damage_dealt": u.total_damage_dealt,
            "damage_taken": u.total_damage_taken,
            "healing_done": u.total_healing_done,
        })
    return stats


def serialize_env(env: FantasyEnv) -> dict:
    terrain = [[{"type": "open", "elevation": 0} for _ in range(env.width)] for _ in range(env.height)]
    return {
        "turn": env.turn,
        "units": [u.to_dict() for u in env.units.values()],
        "events": list(env.events),
        "events_structured": [e.to_dict() for e in env.structured_events],
        "map": {"width": env.width, "height": env.height, "terrain": terrain},
        "stats": compute_stats(env),
        "danger_zones": list(env.danger_zones),
        "team_lb": dict(env.team_lb),
    }


@router.post("/create")
def create_fantasy_battle():
    env = FantasyEnv()
    width, height = 12, 10
    rp = spawn_positions(0, width, height)
    bp = spawn_positions(8, width, height)

    # Frontline: MT, ST, melee DPS; Backline: ranged DPS, healers
    red_front = ["dark_knight", "warrior", "dragoon", "monk"]
    red_back = ["black_mage", "bard", "white_mage", "scholar"]
    blue_front = ["dark_knight", "warrior", "dragoon", "monk"]
    blue_back = ["black_mage", "bard", "white_mage", "scholar"]

    red_jobs = [(k, rp["front"][i]) for i, k in enumerate(red_front)] + \
               [(k, rp["back"][i]) for i, k in enumerate(red_back)]
    blue_jobs = [(k, bp["front"][i]) for i, k in enumerate(blue_front)] + \
                [(k, bp["back"][i]) for i, k in enumerate(blue_back)]
    env.reset(red_jobs, blue_jobs)

    agents = {}
    for uid in env.units:
        agents[uid] = Ff14Agent(env.units[uid])

    import uuid
    bid = str(uuid.uuid4())[:8]
    sessions[bid] = {"env": env, "agents": agents}
    return {"battle_id": bid, "frame": serialize_env(env)}


@router.post("/step/{battle_id}")
def step_fantasy_battle(battle_id: str):
    session = sessions.get(battle_id)
    if not session:
        raise HTTPException(404, "battle not found")
    env: FantasyEnv = session["env"]
    agents: dict = session["agents"]

    actions = []
    for uid, agent in agents.items():
        unit = env.units.get(uid)
        if not unit or not unit.alive:
            continue
        obs = build_obs(unit, env)
        action = agent.choose_action(obs)
        actions.append(action)

    done = env.step(actions)
    return {"frame": serialize_env(env), "done": done}
