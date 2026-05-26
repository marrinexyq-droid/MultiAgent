from .battle_types import Role, Team
from .env import BattlefieldEnv


class BattleJudge:
    WEIGHTS = {
        "elimination_score": 0.30,
        "survival_score": 0.20,
        "objective_score": 0.25,
        "initiative_score": 0.10,
        "coordination_score": 0.15,
    }

    def evaluate(self, env: BattlefieldEnv, memory_red=None, memory_blue=None) -> dict:
        red_agents = {aid: a for aid, a in env.agents.items() if a.team == Team.RED}
        blue_agents = {aid: a for aid, a in env.agents.items() if a.team == Team.BLUE}

        red_alive = sum(1 for a in red_agents.values() if a.alive)
        blue_alive = sum(1 for a in blue_agents.values() if a.alive)

        if red_alive == 0:
            return self._build_hard_end(env, Team.BLUE, "red_eliminated", red_agents, blue_agents, memory_red, memory_blue)
        if blue_alive == 0:
            return self._build_hard_end(env, Team.RED, "blue_eliminated", red_agents, blue_agents, memory_red, memory_blue)

        red_scores = self._team_scores(Team.RED, red_agents, blue_agents, env, memory_red)
        blue_scores = self._team_scores(Team.BLUE, blue_agents, red_agents, env, memory_blue)

        red_total = self._weighted_total(red_scores)
        blue_total = self._weighted_total(blue_scores)

        if red_total > blue_total + 0.02:
            winner = Team.RED
        elif blue_total > red_total + 0.02:
            winner = Team.BLUE
        else:
            winner = None

        reason = "draw"
        if env.stats.should_adjudicate_stalemate():
            reason = "stalemate_adjudication"
        elif winner is not None:
            team_scores = red_scores if winner == Team.RED else blue_scores
            reason = max(team_scores, key=team_scores.get)

        result = {
            "winner": winner,
            "reason": reason,
            "turn": env.turn,
            "red_rate": round(self._survival_rate(red_agents), 2),
            "blue_rate": round(self._survival_rate(blue_agents), 2),
            "red_score": round(red_total, 3),
            "blue_score": round(blue_total, 3),
            "score_breakdown": {
                "red": {key: round(value, 3) for key, value in red_scores.items()},
                "blue": {key: round(value, 3) for key, value in blue_scores.items()},
            },
            "dominant_reason": reason,
            "team_summary": {
                "red": self._team_summary(Team.RED, red_agents, env, memory_red),
                "blue": self._team_summary(Team.BLUE, blue_agents, env, memory_blue),
            },
            "key_turning_points": self._key_turning_points(env),
            "agent_merits": self._agent_merits(env, memory_red, memory_blue),
        }
        return result

    def _build_hard_end(self, env, winner: Team, reason: str, red_agents, blue_agents, memory_red, memory_blue) -> dict:
        red_scores = self._team_scores(Team.RED, red_agents, blue_agents, env, memory_red)
        blue_scores = self._team_scores(Team.BLUE, blue_agents, red_agents, env, memory_blue)
        if winner == Team.RED:
            red_scores["elimination_score"] = 1.0
        else:
            blue_scores["elimination_score"] = 1.0
        return {
            "winner": winner,
            "reason": reason,
            "turn": env.turn,
            "red_rate": round(self._survival_rate(red_agents), 2),
            "blue_rate": round(self._survival_rate(blue_agents), 2),
            "red_score": round(self._weighted_total(red_scores), 3),
            "blue_score": round(self._weighted_total(blue_scores), 3),
            "score_breakdown": {
                "red": {key: round(value, 3) for key, value in red_scores.items()},
                "blue": {key: round(value, 3) for key, value in blue_scores.items()},
            },
            "dominant_reason": reason,
            "team_summary": {
                "red": self._team_summary(Team.RED, red_agents, env, memory_red),
                "blue": self._team_summary(Team.BLUE, blue_agents, env, memory_blue),
            },
            "key_turning_points": self._key_turning_points(env),
            "agent_merits": self._agent_merits(env, memory_red, memory_blue),
        }

    def _survival_rate(self, agents: dict) -> float:
        total_hp = sum(a.hp for a in agents.values() if a.alive)
        max_hp = sum(a.max_hp for a in agents.values())
        return total_hp / max_hp if max_hp > 0 else 0.0

    def _alive_ratio(self, agents: dict) -> float:
        alive = sum(1 for a in agents.values() if a.alive)
        return alive / len(agents) if agents else 0.0

    def _weighted_total(self, team_scores: dict) -> float:
        return sum(team_scores[key] * weight for key, weight in self.WEIGHTS.items())

    def _team_scores(self, team: Team, own_agents: dict, enemy_agents: dict, env: BattlefieldEnv, memory_pool) -> dict:
        records = [record for record in env.stats.agent_records.values() if record.team == team]
        enemy_records = [record for record in env.stats.agent_records.values() if record.team != team]
        total_damage = sum(record.damage_dealt for record in records)
        total_kills = sum(record.kills for record in records)
        max_enemy_hp = sum(agent.max_hp for agent in enemy_agents.values()) or 1
        elimination_score = min(1.0, (total_damage / max_enemy_hp) * 0.75 + (total_kills / max(1, len(enemy_agents))) * 0.25)

        survival_score = min(1.0, self._survival_rate(own_agents) * 0.6 + self._alive_ratio(own_agents) * 0.4)

        team_control = env.stats.team_control_turns[team]
        enemy_control = env.stats.team_control_turns[Team.BLUE if team == Team.RED else Team.RED]
        control_total = max(1, team_control + enemy_control)
        control_score = team_control / control_total
        task_total = max(1, env.stats.team_task_assignments[team])
        task_completion_score = min(1.0, env.stats.team_task_completions[team] / task_total)
        objective_score = min(1.0, control_score * 0.6 + task_completion_score * 0.4)

        first_spot_turn = env.stats.team_first_spot_turn[team]
        enemy_first_spot_turn = env.stats.team_first_spot_turn[Team.BLUE if team == Team.RED else Team.RED]
        first_spot_score = 0.5
        if first_spot_turn is not None and (enemy_first_spot_turn is None or first_spot_turn < enemy_first_spot_turn):
            first_spot_score = 1.0
        elif first_spot_turn is None and enemy_first_spot_turn is not None:
            first_spot_score = 0.0
        report_total = max(1, env.stats.team_reports[team] + env.stats.team_reports[Team.BLUE if team == Team.RED else Team.RED])
        report_score = env.stats.team_reports[team] / report_total
        initiative_score = min(1.0, first_spot_score * 0.55 + report_score * 0.45)

        high_conf = env.stats.team_high_confidence_reports[team]
        coord_actions = sum(record.coordination_contributions for record in records)
        skill_uses = env.stats.team_skill_uses[team]
        coordination_score = min(1.0, (high_conf * 0.15) + (coord_actions * 0.2) + (skill_uses * 0.05))

        if memory_pool and memory_pool.read_summary():
            summary = memory_pool.read_summary()
            if summary.get("memory_health") == "fresh":
                initiative_score = min(1.0, initiative_score + 0.05)
            if summary.get("active_tasks", 0) > 0:
                coordination_score = min(1.0, coordination_score + 0.05)

        return {
            "elimination_score": round(elimination_score, 4),
            "survival_score": round(survival_score, 4),
            "objective_score": round(objective_score, 4),
            "initiative_score": round(initiative_score, 4),
            "coordination_score": round(coordination_score, 4),
        }

    def _team_summary(self, team: Team, agents: dict, env: BattlefieldEnv, memory_pool) -> dict:
        summary = memory_pool.read_summary() if memory_pool else {}
        return {
            "alive_units": sum(1 for agent in agents.values() if agent.alive),
            "survival_rate": round(self._survival_rate(agents), 2),
            "control_turns": env.stats.team_control_turns[team],
            "reports": env.stats.team_reports[team],
            "tasks_completed": env.stats.team_task_completions[team],
            "memory_focus": summary.get("recommended_focus") if summary else None,
        }

    def _agent_merits(self, env: BattlefieldEnv, memory_red, memory_blue) -> dict[str, dict]:
        results = {}
        for agent_id, record in env.stats.agent_records.items():
            memory_pool = memory_red if record.team == Team.RED else memory_blue
            memory_view = memory_pool.read(agent_id) if memory_pool else {}
            score = self._merit_score(record)
            commendations = self._commendations(record, memory_view)
            results[agent_id] = {
                "team": record.team.value,
                "role": record.role.value,
                "merit_score": round(score, 2),
                "commendations": commendations,
                "explanation": self._merit_explanation(record),
                "stats": {
                    "damage_dealt": record.damage_dealt,
                    "damage_taken": record.damage_taken,
                    "kills": record.kills,
                    "assists": record.assists,
                    "enemy_spotted": record.enemy_spotted,
                    "first_spots": record.first_spots,
                    "high_confidence_reports": record.high_confidence_reports,
                    "used_reports": record.used_reports,
                    "decisive_reports": record.decisive_reports,
                    "tasks_assigned": record.tasks_assigned,
                    "used_task_assignments": record.used_task_assignments,
                    "tasks_completed": record.tasks_completed,
                    "control_turns": record.control_turns,
                    "holds_under_pressure": record.holds_under_pressure,
                    "targeted_strikes": record.targeted_strikes,
                    "skill_uses": record.skill_uses,
                    "turns_alive": record.turns_alive,
                },
            }
        return dict(sorted(results.items(), key=lambda item: item[1]["merit_score"], reverse=True))

    def _key_turning_points(self, env: BattlefieldEnv) -> list[dict]:
        turning = []
        priority_types = {"SPOT", "BLOCK", "ENGAGE", "JAM", "RESULT"}
        for event in env.structured_events:
            if event.type not in priority_types:
                continue
            turning.append(
                {
                    "turn": event.turn,
                    "type": event.type,
                    "summary": event.summary,
                    "actor_id": event.actor_id,
                    "target_id": event.target_id,
                    "target_position": event.target_position,
                }
            )
        return turning[:8]

    def _merit_score(self, record) -> float:
        if record.role == Role.COORDINATOR:
            return (
                record.tasks_assigned * 8
                + record.used_task_assignments * 14
                + record.coordination_contributions * 10
                + record.high_confidence_reports * 4
                + record.used_reports * 5
                + record.turns_alive * 1.2
                - record.blocked_moves * 1.5
            )
        if record.role == Role.SCOUT:
            return (
                record.enemy_spotted * 5
                + record.first_spots * 12
                + record.high_confidence_reports * 7
                + record.used_reports * 12
                + record.decisive_reports * 18
                + record.turns_alive * 1.0
            )
        if record.role == Role.ATTACKER:
            return (
                record.damage_dealt * 0.6
                + record.kills * 18
                + record.assists * 8
                + record.tasks_completed * 10
                + record.targeted_strikes * 6
            )
        if record.role == Role.SUPPORT:
            return (
                record.tasks_completed * 8
                + record.coordination_contributions * 8
                + record.skill_uses * 6
                + record.turns_alive * 1.4
            )
        if record.role == Role.JAMMER:
            return (
                record.used_reports * 8
                + record.coordination_contributions * 7
                + record.skill_uses * 6
                + record.turns_alive * 1.1
            )
        if record.role == Role.CONTROLLER:
            return (
                record.control_turns * 8
                + record.holds_under_pressure * 8
                + record.skill_uses * 6
                + record.turns_alive * 1.2
            )
        if record.role == Role.ASSAULTER:
            return (
                record.damage_dealt * 0.55
                + record.kills * 16
                + record.targeted_strikes * 10
                + record.turns_alive * 0.8
            )
        return (
            record.damage_taken * 0.35
            + record.control_turns * 7
            + record.holds_under_pressure * 8
            + record.tasks_completed * 5
            + record.turns_alive * 1.4
        )

    def _merit_explanation(self, record) -> str:
        if record.role == Role.COORDINATOR:
            return (
                f"分配任务 {record.tasks_assigned} 次，其中 {record.used_task_assignments} 次进入执行；"
                f"协同贡献 {record.coordination_contributions} 次，有效情报 {record.used_reports} 条。"
            )
        if record.role == Role.SCOUT:
            return (
                f"发现目标 {record.enemy_spotted} 个，首次发现 {record.first_spots} 次；"
                f"被利用情报 {record.used_reports} 条，形成战果 {record.decisive_reports} 条。"
            )
        if record.role == Role.ATTACKER:
            return (
                f"累计输出 {record.damage_dealt}，击杀 {record.kills}，助攻 {record.assists}；"
                f"重点打击 {record.targeted_strikes} 次，完成任务 {record.tasks_completed} 次。"
            )
        if record.role == Role.SUPPORT:
            return f"技能使用 {record.skill_uses} 次，维持关键单位 {record.tasks_completed} 次，协同支撑 {record.coordination_contributions} 次。"
        if record.role == Role.JAMMER:
            return f"干扰技能 {record.skill_uses} 次，有效扰乱 {record.used_reports} 条，协同打乱 {record.coordination_contributions} 次。"
        if record.role == Role.CONTROLLER:
            return f"控制区驻守 {record.control_turns} 回合，高压封锁 {record.holds_under_pressure} 次，技能使用 {record.skill_uses} 次。"
        if record.role == Role.ASSAULTER:
            return f"累计输出 {record.damage_dealt}，击杀 {record.kills}，破局打击 {record.targeted_strikes} 次。"
        return (
            f"承受影响 {record.damage_taken}，控制区驻守 {record.control_turns} 回合；"
            f"高压守点 {record.holds_under_pressure} 次，完成任务 {record.tasks_completed} 次。"
        )

    def _commendations(self, record, memory_view: dict) -> list[str]:
        badges = []
        if record.role == Role.COORDINATOR:
            if record.used_task_assignments >= 2:
                badges.append("战术中枢")
            if record.coordination_contributions >= 2:
                badges.append("任务调度者")
        elif record.role == Role.SCOUT:
            if record.first_spots >= 1:
                badges.append("先导观察者")
            if record.decisive_reports >= 1 or record.used_reports >= 2:
                badges.append("敌情捕手")
        elif record.role == Role.ATTACKER:
            if record.kills >= 1:
                badges.append("突破先锋")
            if record.damage_dealt >= 40 or record.targeted_strikes >= 2:
                badges.append("火力核心")
        elif record.role == Role.DEFENDER:
            if record.control_turns >= 2 or record.holds_under_pressure >= 1:
                badges.append("阵线锚点")
            if record.damage_taken >= 20 or record.holds_under_pressure >= 2:
                badges.append("稳固壁垒")
        elif record.role == Role.SUPPORT:
            if record.skill_uses >= 2:
                badges.append("续航维持者")
            if record.coordination_contributions >= 2:
                badges.append("后场支柱")
        elif record.role == Role.JAMMER:
            if record.skill_uses >= 2:
                badges.append("链路扰断者")
            if record.used_reports >= 1:
                badges.append("节奏破坏者")
        elif record.role == Role.CONTROLLER:
            if record.control_turns >= 2:
                badges.append("区域封锁者")
            if record.holds_under_pressure >= 1:
                badges.append("路径压制者")
        elif record.role == Role.ASSAULTER:
            if record.kills >= 1:
                badges.append("破局切入者")
            if record.targeted_strikes >= 2:
                badges.append("后排猎手")

        if not badges and memory_view.get("summary", {}).get("memory_health") == "fresh":
            badges.append("态势支撑者")
        return badges[:2] or ["常规贡献"]
