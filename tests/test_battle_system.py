import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - depends on local runtime
    TestClient = None

from src.battle.battle_types import Action, ActionType, AgentState, Message, Position, Role, Team
from src.battle.config import config
from src.battle.env import BattlefieldEnv
from src.battle.judge import BattleJudge
from src.battle.memory import SharedMemoryPool
from src.battle.roster import ROLE_TEMPLATES, build_agents_from_team_config, default_scenario_config, default_team_config
from src.battle.runner import create_agents, main
from src.battle.battle_ui_v3 import _build_advice_items, _record_visible_enemy_contacts


class BattleSystemTests(unittest.TestCase):
    def setUp(self):
        self._original_api_key = config.api_key
        config.api_key = None
        self.client = None
        if TestClient is not None:
            from src.battle.api_server import app

            self.client = TestClient(app)

    def tearDown(self):
        config.api_key = self._original_api_key

    def test_memory_pool_write_read_and_decay(self):
        memory = SharedMemoryPool(Team.RED)
        msg = Message(
            msg_id="msg-1",
            sender_id="red_scout",
            sender_role=Role.SCOUT,
            content={"type": "enemy_spot", "target_id": "blue_1", "pos": {"x": 5, "y": 5}, "hp": 80},
            timestamp=1,
        )

        self.assertTrue(memory.write(msg))
        self.assertFalse(memory.write(msg))
        self.assertIn("blue_1", memory.read("red_striker")["enemy_tracks"])

        for _ in range(10):
            memory.decay()

        self.assertEqual(memory.read("red_striker")["enemy_tracks"], {})

    def test_memory_pool_v3_builds_beliefs_and_summary(self):
        memory = SharedMemoryPool(Team.RED)
        scout_msg = Message(
            msg_id="msg-2",
            sender_id="red_probe",
            sender_role=Role.SCOUT,
            content={"type": "enemy_spot", "target_id": "blue_guard_1", "pos": {"x": 6, "y": 5}, "hp": 100},
            timestamp=3,
        )
        attacker_msg = Message(
            msg_id="msg-3",
            sender_id="red_striker",
            sender_role=Role.ATTACKER,
            content={"type": "enemy_spot", "target_id": "blue_guard_1", "pos": {"x": 6, "y": 5}, "hp": 95},
            timestamp=4,
        )

        memory.write(scout_msg)
        memory.write(attacker_msg)

        view = memory.read("red_coordinator")
        self.assertIn("beliefs", view)
        self.assertIn("summary", view)
        self.assertIn("blue_guard_1", view["beliefs"])
        self.assertEqual(view["summary"]["primary_threat"], "blue_guard_1")
        self.assertGreaterEqual(view["beliefs"]["blue_guard_1"]["source_count"], 2)

    def test_memory_pool_v3_tracks_task_status_and_legacy_view(self):
        memory = SharedMemoryPool(Team.RED)
        task_msg = Message(
            msg_id="msg-4",
            sender_id="red_coordinator",
            sender_role=Role.COMMANDER,
            content={
                "type": "task_assign",
                "task_id": "task-1",
                "assignee": "red_striker",
                "task": "压制前沿目标",
                "task_type": "engage",
                "target_id": "blue_guard_1",
                "target_pos": {"x": 6, "y": 5},
                "priority": "high",
            },
            timestamp=5,
        )

        memory.write(task_msg)
        view = memory.read("red_striker")

        self.assertIn("tasks", view)
        self.assertIn("team_tasks", view)
        self.assertIn("task-1", view["tasks"])
        self.assertIn("task-1", view["team_tasks"])
        self.assertEqual(view["tasks"]["task-1"]["status"], "pending")
        self.assertEqual(view["team_tasks"]["task-1"]["target_id"], "blue_guard_1")

    def test_report_usage_and_task_progress_feed_merit_stats(self):
        env = BattlefieldEnv(grid_size=8)
        red_cmd = AgentState("red_coordinator", Team.RED, Role.COMMANDER, Position(1, 1))
        red_atk = AgentState("red_striker", Team.RED, Role.ATTACKER, Position(2, 1), attack_power=40)
        blue_def = AgentState("blue_guard_1", Team.BLUE, Role.DEFENDER, Position(3, 1), hp=100, max_hp=100)
        env.reset([red_cmd, red_atk], [blue_def])
        memory_red = SharedMemoryPool(Team.RED, battle_stats=env.stats)

        report = Message(
            msg_id="intel-1",
            sender_id="red_coordinator",
            sender_role=Role.COMMANDER,
            content={"type": "enemy_spot", "target_id": "blue_guard_1", "pos": {"x": 3, "y": 1}, "hp": 100},
            timestamp=1,
        )
        task = Message(
            msg_id="task-msg-1",
            sender_id="red_coordinator",
            sender_role=Role.COMMANDER,
            content={
                "type": "task_assign",
                "task_id": "task-1",
                "assignee": "red_striker",
                "task": "突破蓝方前沿",
                "target_id": "blue_guard_1",
                "target_pos": {"x": 3, "y": 1},
            },
            timestamp=1,
        )

        memory_red.write(report)
        memory_red.write(task)
        memory_red.update_task_progress(env.agents, turn=1)
        env.step([Action("red_striker", ActionType.ATTACK, target_id="blue_guard_1")])

        cmd_record = env.stats.agent_records["red_coordinator"]
        atk_record = env.stats.agent_records["red_striker"]
        self.assertGreaterEqual(cmd_record.used_reports, 1)
        self.assertGreaterEqual(cmd_record.used_task_assignments, 1)
        self.assertGreaterEqual(atk_record.targeted_strikes, 1)

    def test_env_blocks_overlapping_moves(self):
        env = BattlefieldEnv(grid_size=8)
        red_a = AgentState("red_a", Team.RED, Role.ATTACKER, Position(1, 1))
        red_b = AgentState("red_b", Team.RED, Role.ATTACKER, Position(3, 1))
        blue_a = AgentState("blue_a", Team.BLUE, Role.DEFENDER, Position(6, 6))
        env.reset([red_a, red_b], [blue_a])

        actions = [
            Action("red_a", ActionType.MOVE, target=Position(2, 1)),
            Action("red_b", ActionType.MOVE, target=Position(2, 1)),
        ]
        env.step(actions)

        positions = {
            agent_id: (agent.pos.x, agent.pos.y)
            for agent_id, agent in env.agents.items()
            if agent.alive
        }
        alive_positions = list(positions.values())

        self.assertEqual(len(alive_positions), len(set(alive_positions)))
        self.assertIn("[位置阻塞]", "\n".join(env.events))

    def test_judge_picks_elimination_before_rates(self):
        env = BattlefieldEnv(grid_size=8)
        red_a = AgentState("red_a", Team.RED, Role.ATTACKER, Position(1, 1), hp=100, max_hp=100)
        blue_a = AgentState("blue_a", Team.BLUE, Role.DEFENDER, Position(6, 6), hp=0, max_hp=100, alive=False)
        env.reset([red_a], [blue_a])

        result = BattleJudge().evaluate(env)

        self.assertEqual(result["winner"], Team.RED)
        self.assertEqual(result["reason"], "blue_eliminated")

    def test_judge_returns_score_breakdown_and_merits(self):
        env = BattlefieldEnv(grid_size=8)
        red_a = AgentState("red_probe", Team.RED, Role.SCOUT, Position(1, 1), hp=80, max_hp=80)
        blue_a = AgentState("blue_guard", Team.BLUE, Role.DEFENDER, Position(6, 6), hp=100, max_hp=100)
        env.reset([red_a], [blue_a])
        env.stats.record_scout_spot("red_probe", ["blue_guard"], turn=1)
        env.stats.record_turn_presence(env.agents, env._control_points())
        env.stats.finalize_turn()

        result = BattleJudge().evaluate(env)

        self.assertIn("score_breakdown", result)
        self.assertIn("agent_merits", result)
        self.assertIn("red_probe", result["agent_merits"])
        self.assertIn("initiative_score", result["score_breakdown"]["red"])
        self.assertIn("explanation", result["agent_merits"]["red_probe"])

    def test_env_stalemate_triggers_termination(self):
        env = BattlefieldEnv(grid_size=8)
        red_a = AgentState("red_a", Team.RED, Role.ATTACKER, Position(1, 1))
        blue_a = AgentState("blue_a", Team.BLUE, Role.DEFENDER, Position(6, 6))
        env.reset([red_a], [blue_a])

        done = False
        for _ in range(7):
            _, done = env.step([])
            if done:
                break

        self.assertTrue(done)
        self.assertIn("僵局", "\n".join(env.events))

    def test_v3_visible_enemy_detection_updates_blue_memory(self):
        env = BattlefieldEnv(grid_size=8)
        red_a = AgentState("red_a", Team.RED, Role.ATTACKER, Position(1, 1), vision_range=3)
        blue_a = AgentState("blue_a", Team.BLUE, Role.DEFENDER, Position(3, 1), vision_range=3)
        env.reset([red_a], [blue_a])
        agents = {
            "red_a": type("StubAgent", (), {"state": red_a})(),
            "blue_a": type("StubAgent", (), {"state": blue_a})(),
        }
        memory_red = SharedMemoryPool(Team.RED, battle_stats=env.stats)
        memory_blue = SharedMemoryPool(Team.BLUE, battle_stats=env.stats)

        written = _record_visible_enemy_contacts(agents, env, memory_red, memory_blue, 1)

        self.assertGreaterEqual(written, 2)
        self.assertIn("red_a", memory_blue.read("blue_a")["enemy_tracks"])

    def test_v3_builds_structured_advice_items(self):
        env = BattlefieldEnv(grid_size=8)
        red_a = AgentState("red_probe", Team.RED, Role.SCOUT, Position(1, 1), vision_range=4)
        blue_a = AgentState("blue_guard_1", Team.BLUE, Role.DEFENDER, Position(3, 1), vision_range=2)
        env.reset([red_a], [blue_a])
        memory_red = SharedMemoryPool(Team.RED, battle_stats=env.stats)
        memory_blue = SharedMemoryPool(Team.BLUE, battle_stats=env.stats)
        memory_red.write(
            Message(
                msg_id="advice-msg-1",
                sender_id="red_probe",
                sender_role=Role.SCOUT,
                content={"type": "enemy_spot", "target_id": "blue_guard_1", "pos": {"x": 3, "y": 1}, "hp": 100},
                timestamp=1,
            )
        )

        advice_items = _build_advice_items(env, memory_red, memory_blue)

        self.assertTrue(advice_items)
        self.assertIn("rendered_text", advice_items[0])

    def test_runner_main_creates_log_file(self):
        original_log_dir = config.log_dir
        original_max_turns = config.max_turns
        original_api_key = config.api_key

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                config.log_dir = tmpdir
                config.max_turns = 1
                config.api_key = None

                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    main()

                files = os.listdir(tmpdir)
                self.assertEqual(len(files), 1)
                log_path = os.path.join(tmpdir, files[0])
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()

                self.assertIn("多智能体对抗演练系统 - Phase 1 MVP", stdout.getvalue())
                self.assertIn("演练结果", content)
            finally:
                config.log_dir = original_log_dir
                config.max_turns = original_max_turns
                config.api_key = original_api_key

    def test_api_roles_endpoint_returns_templates(self):
        if self.client is None:
            self.skipTest("fastapi not available in current python runtime")
        response = self.client.get("/api/roles")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("roles", payload)
        self.assertIn("coordinator", payload["roles"])
        self.assertIn("default_scenario_config", payload)
        self.assertEqual(len(payload["roles"]), 8)
        self.assertIn("group", payload["roles"]["coordinator"])
        self.assertIn("defaults", payload["roles"]["coordinator"])
        self.assertIn("target_preference_options", payload["roles"]["coordinator"])

    def test_api_battle_frames_endpoint_returns_frames(self):
        if self.client is None:
            self.skipTest("fastapi not available in current python runtime")
        create = self.client.post("/api/battles", json={"mode": "演练后回放", "max_turns": 10})
        self.assertEqual(create.status_code, 200)
        battle_id = create.json()["battle_id"]

        frames = self.client.get(f"/api/battles/{battle_id}/frames")
        self.assertEqual(frames.status_code, 200)
        payload = frames.json()
        self.assertIn("frames", payload)
        self.assertTrue(payload["frames"])
        self.assertIn("summary", payload)
        self.assertIn("events_structured", payload["frames"][0])
        self.assertIn("timeline_markers", payload["frames"][0])
        self.assertIn("effect_details", payload["frames"][0])
        self.assertIn("status_flags", payload["frames"][0]["units"][0])

    def test_create_agents_returns_expected_teams(self):
        agents, red_states, blue_states = create_agents()

        self.assertEqual(len(agents), 5)
        self.assertEqual(len(red_states), 3)
        self.assertEqual(len(blue_states), 2)
        self.assertTrue(all(agent.team == Team.RED for agent in red_states))
        self.assertTrue(all(agent.team == Team.BLUE for agent in blue_states))

    def test_role_templates_have_expected_advantages(self):
        coordinator = ROLE_TEMPLATES[Role.COORDINATOR]
        scout = ROLE_TEMPLATES[Role.SCOUT]
        attacker = ROLE_TEMPLATES[Role.ATTACKER]
        defender = ROLE_TEMPLATES[Role.DEFENDER]
        support = ROLE_TEMPLATES[Role.SUPPORT]
        controller = ROLE_TEMPLATES[Role.CONTROLLER]

        self.assertGreaterEqual(coordinator.vision_range, attacker.vision_range)
        self.assertGreater(scout.move_speed, attacker.move_speed - 1)
        self.assertGreater(scout.vision_range, attacker.vision_range)
        self.assertGreater(attacker.attack_power, scout.attack_power)
        self.assertGreater(defender.hp, attacker.hp)
        self.assertGreater(support.ammo, attacker.ammo)
        self.assertGreaterEqual(controller.attack_range, attacker.attack_range)

    def test_build_agents_from_team_config_assigns_unique_positions(self):
        team_config = default_team_config()
        team_config[Team.RED][Role.DEFENDER]["count"] = 1
        team_config[Team.BLUE][Role.SCOUT]["count"] = 1

        agents, red_states, blue_states = build_agents_from_team_config(team_config, scenario_config=default_scenario_config(10, 8))

        self.assertEqual(len(agents), len(red_states) + len(blue_states))
        positions = [(state.pos.x, state.pos.y) for state in red_states + blue_states]
        self.assertEqual(len(positions), len(set(positions)))
        self.assertTrue(all(state.agent_id.startswith("red_") for state in red_states))
        self.assertTrue(all(state.agent_id.startswith("blue_") for state in blue_states))

    def test_build_agents_from_team_config_uses_rectangular_scenario(self):
        team_config = default_team_config()
        agents, red_states, blue_states = build_agents_from_team_config(team_config, scenario_config=default_scenario_config(12, 8))

        self.assertEqual(len(agents), len(red_states) + len(blue_states))
        self.assertTrue(all(0 <= state.pos.x < 12 and 0 <= state.pos.y < 8 for state in red_states + blue_states))

    def test_default_team_config_includes_ai_preferences(self):
        team_config = default_team_config()
        red_attacker = team_config[Team.RED][Role.ATTACKER]
        self.assertIn("task_priority", red_attacker)
        self.assertIn("target_preference", red_attacker)
        self.assertIn("risk_preference", red_attacker)
        self.assertIn("skill_trigger_threshold", red_attacker)

    def test_attacker_skill_and_cooldown_work(self):
        env = BattlefieldEnv(grid_size=8)
        red_a = AgentState(
            "red_a", Team.RED, Role.ATTACKER, Position(1, 1),
            attack_power=30, skill_name="强袭", skill_cooldown=3
        )
        blue_a = AgentState("blue_a", Team.BLUE, Role.DEFENDER, Position(2, 1), hp=120, max_hp=120)
        env.reset([red_a], [blue_a])

        env.step([Action("red_a", ActionType.SKILL, target_id="blue_a", skill_id="power_strike")])

        self.assertLess(env.agents["blue_a"].hp, 120)
        self.assertGreater(env.agents["red_a"].skill_cooldown_remaining, 0)

    def test_defender_skill_reduces_damage(self):
        env = BattlefieldEnv(grid_size=8)
        red_a = AgentState("red_a", Team.RED, Role.ATTACKER, Position(1, 1), attack_power=20)
        blue_a = AgentState(
            "blue_a", Team.BLUE, Role.DEFENDER, Position(2, 1), hp=100, max_hp=100,
            skill_name="固守", skill_cooldown=4
        )
        env.reset([red_a], [blue_a])

        env.step([
            Action("blue_a", ActionType.SKILL, skill_id="fortify"),
            Action("red_a", ActionType.ATTACK, target_id="blue_a"),
        ])

        self.assertGreater(env.agents["blue_a"].hp, 70)


if __name__ == "__main__":
    unittest.main()
