import io
import os
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - depends on local runtime
    TestClient = None

from src.battle.battle_types import Action, ActionType, AgentState, Message, Position, RectZone, Role, ScenarioConfig, Team, TerrainCell, TerrainType
from src.battle.config import BattleConfig, config
from src.battle.env import BattlefieldEnv
from src.battle.eval_runner import build_default_scenarios, run_evaluation
from src.battle.judge import BattleJudge
from src.battle.llm_actions import parse_llm_action_response
from src.battle.memory import SharedMemoryPool
from src.battle.roster import ROLE_TEMPLATES, build_agents_from_team_config, default_scenario_config, default_team_config
from src.battle.runner import create_agents, main
from src.battle.runtime_advice import _build_advice_items, _record_visible_enemy_contacts


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
        scenario = ScenarioConfig(
            width=8,
            height=8,
            red_spawn_zones=[RectZone(0, 0, 3, 8)],
            blue_spawn_zones=[RectZone(5, 0, 3, 8)],
            control_zones=[RectZone(3, 3, 2, 2)],
            terrain_grid=[[TerrainCell(TerrainType.OPEN) for _ in range(8)] for _ in range(8)],
        )
        env = BattlefieldEnv(scenario_config=scenario)
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

    def test_api_latest_evaluation_returns_report(self):
        if self.client is None:
            self.skipTest("fastapi not available in current python runtime")
        from src.battle import api_server

        original_path = api_server.LATEST_EVAL_REPORT
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "eval_latest.json"
            report_path.write_text(
                '{"generated_at":"2026-06-06T00:00:00Z","seed":7,"runs_per_scenario":1,"policies":["rule_only"],"scenarios":["balanced_square"],"summary":{},"runs":[]}',
                encoding="utf-8",
            )
            try:
                api_server.LATEST_EVAL_REPORT = report_path
                response = self.client.get("/api/evaluations/latest")
            finally:
                api_server.LATEST_EVAL_REPORT = original_path

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["policies"], ["rule_only"])
        self.assertEqual(payload["scenarios"], ["balanced_square"])

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
        self.assertIn("llm_mode_enabled", payload["frames"][0])
        self.assertIn("llm_decision_traces", payload["frames"][0])
        self.assertFalse(payload["frames"][0]["llm_mode_enabled"])
        self.assertEqual(payload["frames"][0]["llm_decision_traces"], [])

    def test_battle_storage_persists_initial_frame_and_completed_summary(self):
        from src.battle.api_runtime import BattleSessionManager
        from src.battle.storage import BattleStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = BattleStorage(Path(tmpdir) / "battles.sqlite3")
            local_manager = BattleSessionManager(storage=storage)
            session = local_manager.create_session("replay", 3)
            battle_id = session.battle_id

            run = storage.load_run(battle_id)
            self.assertIsNotNone(run)
            self.assertEqual(run["frame_count"], 1)
            self.assertEqual(len(storage.load_frames(battle_id)), 1)

            session.run_all()
            completed = storage.load_run(battle_id)
            self.assertEqual(completed["status"], "done")
            self.assertGreaterEqual(completed["frame_count"], 2)
            self.assertIsNotNone(completed["summary"])
            self.assertIn("result", completed["summary"])
            self.assertIn("red_score", completed["summary"]["result"])
            self.assertIn("blue_score", completed["summary"]["result"])

    def test_battle_storage_restores_frames_after_memory_session_is_cleared(self):
        from src.battle.api_runtime import BattleSessionManager
        from src.battle.storage import BattleStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = BattleStorage(Path(tmpdir) / "battles.sqlite3")
            local_manager = BattleSessionManager(storage=storage)
            session = local_manager.create_session("replay", 2)
            battle_id = session.battle_id
            expected_frames = session.run_all()

            local_manager.sessions.clear()
            restored = local_manager.get(battle_id)

            restored_frames = restored.run_all()
            self.assertEqual(len(restored_frames), len(expected_frames))
            self.assertEqual(restored_frames[0]["turn"], expected_frames[0]["turn"])
            self.assertEqual(restored_frames[-1]["turn"], expected_frames[-1]["turn"])
            self.assertEqual(restored.summary_payload()["battle_id"], battle_id)
            self.assertEqual(restored.summary_payload()["status"], "done")

    def test_api_battle_history_lists_persisted_results(self):
        if self.client is None:
            self.skipTest("fastapi not available in current python runtime")
        from src.battle import api_server
        from src.battle.api_runtime import BattleSessionManager
        from src.battle.storage import BattleStorage

        original_manager = api_server.manager
        with tempfile.TemporaryDirectory() as tmpdir:
            api_server.manager = BattleSessionManager(storage=BattleStorage(Path(tmpdir) / "battles.sqlite3"))
            try:
                create = self.client.post("/api/battles", json={"mode": "replay", "max_turns": 2})
                self.assertEqual(create.status_code, 200)
                battle_id = create.json()["battle_id"]
                frames = self.client.get(f"/api/battles/{battle_id}/frames")
                self.assertEqual(frames.status_code, 200)

                api_server.manager.sessions.clear()
                restored_frames = self.client.get(f"/api/battles/{battle_id}/frames")
                restored_summary = self.client.get(f"/api/battles/{battle_id}/summary")
                history = self.client.get("/api/battles")
            finally:
                api_server.manager = original_manager

        self.assertEqual(restored_frames.status_code, 200)
        self.assertTrue(restored_frames.json()["frames"])
        self.assertEqual(restored_summary.status_code, 200)
        self.assertEqual(restored_summary.json()["battle_id"], battle_id)
        self.assertEqual(history.status_code, 200)
        battles = history.json()["battles"]
        self.assertEqual(battles[0]["battle_id"], battle_id)
        self.assertEqual(battles[0]["status"], "done")
        self.assertIn("winner", battles[0])
        self.assertIn("red_score", battles[0])
        self.assertIn("blue_score", battles[0])

    def test_api_pause_resume_routes_update_live_session(self):
        if self.client is None:
            self.skipTest("fastapi not available in current python runtime")
        create = self.client.post("/api/battles", json={"mode": "实时推演", "max_turns": 10})
        self.assertEqual(create.status_code, 200)
        battle_id = create.json()["battle_id"]

        start = self.client.post(f"/api/battles/{battle_id}/start", json={"mode": "实时推演"})
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.json()["status"], "running")

        pause = self.client.post(f"/api/battles/{battle_id}/pause")
        self.assertEqual(pause.status_code, 200)
        self.assertEqual(pause.json()["status"], "paused")

        resume = self.client.post(f"/api/battles/{battle_id}/resume")
        self.assertEqual(resume.status_code, 200)
        self.assertEqual(resume.json()["status"], "running")

    def test_stream_battle_waits_while_session_is_paused(self):
        from src.battle.api_runtime import BattleSessionManager, stream_battle

        session = BattleSessionManager().create_session("实时推演", 10)
        events = stream_battle(session)
        first_event = next(events)
        self.assertIn("event: frame", first_event)

        session.pause()
        next_event: list[str] = []
        frame_ready = threading.Event()

        def read_next_event():
            next_event.append(next(events))
            frame_ready.set()

        thread = threading.Thread(target=read_next_event, daemon=True)
        thread.start()
        time.sleep(0.2)
        self.assertFalse(frame_ready.is_set())

        session.resume()
        self.assertTrue(frame_ready.wait(2))
        self.assertIn("event: frame", next_event[0])

    def test_structured_frames_expose_llm_decision_traces(self):
        from src.battle.api_runtime import BattleSessionManager

        session = BattleSessionManager().create_session("演练后回放", 1)

        initial_frame = session.frames[0]
        self.assertFalse(initial_frame["llm_mode_enabled"])
        self.assertEqual(initial_frame["llm_decision_traces"], [])

        for agent in session.agents.values():
            agent.client = object()

        frame, _ = session.step_once(1)

        self.assertTrue(frame["llm_mode_enabled"])
        self.assertTrue(frame["llm_decision_traces"])
        trace = frame["llm_decision_traces"][0]
        self.assertIn("agent_id", trace)
        self.assertIn("latency_ms", trace)
        self.assertIn("total_tokens", trace)
        self.assertIn("raw_completion", trace)
        self.assertIn("json_mode_requested", trace)
        self.assertEqual(trace["fallback_reason"], "llm_call_failed")

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

    def test_config_accepts_openai_compatible_environment(self):
        original = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL"),
            "OPENAI_MODEL": os.environ.get("OPENAI_MODEL"),
        }
        try:
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["OPENAI_BASE_URL"] = "https://example.test/v1"
            os.environ["OPENAI_MODEL"] = "test-model"

            test_config = BattleConfig()

            self.assertEqual(test_config.api_key, "test-key")
            self.assertEqual(test_config.api_base_url, "https://example.test/v1")
            self.assertEqual(test_config.model, "test-model")
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_eval_runner_builds_default_scenarios(self):
        scenarios = build_default_scenarios()

        self.assertGreaterEqual(len(scenarios), 3)
        self.assertIn("balanced_square", {scenario.name for scenario in scenarios})
        self.assertTrue(all(scenario.team_config for scenario in scenarios))
        self.assertTrue(all(scenario.scenario_config for scenario in scenarios))

    def test_eval_runner_returns_metric_report(self):
        scenarios = build_default_scenarios()[:1]

        report = run_evaluation(runs=1, policies=["rule_only"], scenarios=scenarios, seed=7)

        self.assertEqual(report["runs_per_scenario"], 1)
        self.assertEqual(report["policies"], ["rule_only"])
        self.assertEqual(len(report["runs"]), 1)
        run = report["runs"][0]
        self.assertIn("task_completion_rate", run)
        self.assertIn("invalid_action_rate", run)
        self.assertIn("rule_only", report["summary"])
        self.assertIn("overall", report["summary"]["rule_only"])

    def test_llm_action_parser_accepts_valid_move_json(self):
        parsed = parse_llm_action_response(
            '{"action_type":"move","target":{"x":2,"y":3}}',
            agent_id="red_scout_1",
            width=8,
            height=8,
        )

        self.assertTrue(parsed.ok)
        self.assertEqual(parsed.action.action_type, ActionType.MOVE)
        self.assertEqual(parsed.action.target, Position(2, 3))

    def test_llm_action_parser_falls_back_on_malformed_json(self):
        parsed = parse_llm_action_response(
            "not json",
            agent_id="red_scout_1",
            width=8,
            height=8,
        )

        self.assertFalse(parsed.ok)
        self.assertEqual(parsed.action.action_type, ActionType.HOLD)
        self.assertTrue(parsed.fallback_reason.startswith("invalid_json"))

    def test_llm_action_parser_rejects_out_of_bounds_move(self):
        parsed = parse_llm_action_response(
            '{"action_type":"move","target":{"x":99,"y":3}}',
            agent_id="red_scout_1",
            width=8,
            height=8,
        )

        self.assertFalse(parsed.ok)
        self.assertEqual(parsed.action.action_type, ActionType.HOLD)
        self.assertEqual(parsed.fallback_reason, "move_target_out_of_bounds")

    def test_llm_action_parser_rejects_unknown_target(self):
        parsed = parse_llm_action_response(
            '{"action_type":"attack","target_id":"blue_missing"}',
            agent_id="red_attacker_1",
            width=8,
            height=8,
            valid_target_ids={"blue_defender_1"},
        )

        self.assertFalse(parsed.ok)
        self.assertEqual(parsed.action.action_type, ActionType.HOLD)
        self.assertEqual(parsed.fallback_reason, "invalid_target:blue_missing")

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
