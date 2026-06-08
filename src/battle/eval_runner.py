"""Batch evaluation runner for comparing agent policies across scenarios."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from .api_runtime import BattleSessionManager, to_jsonable
from .battle_types import Role, Team
from .config import config
from .roster import default_scenario_config, default_team_config


@dataclass(frozen=True)
class EvaluationScenario:
    """A deterministic scenario definition used by the evaluation harness."""

    name: str
    max_turns: int
    team_config: dict[str, Any]
    scenario_config: dict[str, Any]


def _team_config_to_payload(team_config: dict[Team, dict[Role, dict]]) -> dict[str, Any]:
    return {
        team.value: {
            role.value: dict(spec)
            for role, spec in role_map.items()
        }
        for team, role_map in team_config.items()
    }


def _scenario_payload(width: int, height: int, grid_type: str = "square", terrain_preset: str = "plains") -> dict[str, Any]:
    return default_scenario_config(width, height, grid_type=grid_type, terrain_preset=terrain_preset).to_dict()


def build_default_scenarios() -> list[EvaluationScenario]:
    """Create representative scenarios that stress different team capabilities."""
    balanced = default_team_config()

    scout_pressure = default_team_config()
    scout_pressure[Team.RED][Role.SCOUT]["count"] = 2
    scout_pressure[Team.RED][Role.ATTACKER]["count"] = 1
    scout_pressure[Team.BLUE][Role.DEFENDER]["count"] = 1
    scout_pressure[Team.BLUE][Role.CONTROLLER]["count"] = 1

    assault_breakthrough = default_team_config()
    assault_breakthrough[Team.RED][Role.ASSAULTER]["count"] = 2
    assault_breakthrough[Team.RED][Role.ATTACKER]["count"] = 2
    assault_breakthrough[Team.BLUE][Role.DEFENDER]["count"] = 2
    assault_breakthrough[Team.BLUE][Role.SUPPORT]["count"] = 1

    return [
        EvaluationScenario(
            name="balanced_square",
            max_turns=20,
            team_config=_team_config_to_payload(balanced),
            scenario_config=_scenario_payload(8, 8),
        ),
        EvaluationScenario(
            name="scout_pressure_hex",
            max_turns=20,
            team_config=_team_config_to_payload(scout_pressure),
            scenario_config=_scenario_payload(10, 8, grid_type="hex", terrain_preset="mixed"),
        ),
        EvaluationScenario(
            name="assault_breakthrough",
            max_turns=20,
            team_config=_team_config_to_payload(assault_breakthrough),
            scenario_config=_scenario_payload(10, 8, terrain_preset="urban"),
        ),
    ]


def _with_policy_api_key(policy: str):
    if policy == "rule_only":
        return None
    return config.api_key


def run_single_evaluation(policy: str, scenario: EvaluationScenario, seed: int) -> dict[str, Any]:
    """Run one policy/scenario pair and return normalized metrics."""
    original_api_key = config.api_key
    random_state = random.getstate()
    config.api_key = _with_policy_api_key(policy)
    random.seed(seed)
    try:
        # Policy selection is modeled through the shared config so the normal
        # runtime path is reused instead of maintaining a separate eval engine.
        manager = BattleSessionManager()
        session = manager.create_session(
            mode=f"eval:{policy}",
            max_turns=scenario.max_turns,
            team_config_payload=scenario.team_config,
            scenario_config_payload=scenario.scenario_config,
        )
        session.run_all()
        result = to_jsonable(session.result or {})
        records = session.env.stats.agent_records.values()
        red_records = [record for record in records if record.team == Team.RED]
        blue_records = [record for record in records if record.team == Team.BLUE]
        blocked_moves = sum(record.blocked_moves for record in records)
        agent_turns = sum(record.turns_alive for record in records) or 1
        task_assignments = sum(session.env.stats.team_task_assignments.values())
        task_completions = sum(session.env.stats.team_task_completions.values())

        return {
            "policy": policy,
            "scenario": scenario.name,
            "seed": seed,
            "winner": result.get("winner"),
            "reason": result.get("reason"),
            "turns": result.get("turn", session.env.turn),
            "red_score": result.get("red_score", 0.0),
            "blue_score": result.get("blue_score", 0.0),
            "red_damage_dealt": sum(record.damage_dealt for record in red_records),
            "blue_damage_dealt": sum(record.damage_dealt for record in blue_records),
            "scout_reports_used": sum(record.used_reports for record in records),
            "task_completion_rate": task_completions / max(1, task_assignments),
            "invalid_action_rate": blocked_moves / agent_turns,
            "battle_id": session.battle_id,
        }
    finally:
        config.api_key = original_api_key
        random.setstate(random_state)


def _aggregate_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate raw run rows into dashboard-friendly policy metrics."""
    total = len(runs)
    red_wins = sum(1 for run in runs if run["winner"] == "red")
    blue_wins = sum(1 for run in runs if run["winner"] == "blue")
    draws = total - red_wins - blue_wins
    return {
        "runs": total,
        "red_win_rate": red_wins / max(1, total),
        "blue_win_rate": blue_wins / max(1, total),
        "draw_rate": draws / max(1, total),
        "avg_turns": mean(run["turns"] for run in runs) if runs else 0.0,
        "avg_red_score": mean(run["red_score"] for run in runs) if runs else 0.0,
        "avg_blue_score": mean(run["blue_score"] for run in runs) if runs else 0.0,
        "avg_red_damage": mean(run["red_damage_dealt"] for run in runs) if runs else 0.0,
        "avg_blue_damage": mean(run["blue_damage_dealt"] for run in runs) if runs else 0.0,
        "avg_scout_reports_used": mean(run["scout_reports_used"] for run in runs) if runs else 0.0,
        "avg_task_completion_rate": mean(run["task_completion_rate"] for run in runs) if runs else 0.0,
        "avg_invalid_action_rate": mean(run["invalid_action_rate"] for run in runs) if runs else 0.0,
    }


def run_evaluation(
    runs: int = 20,
    policies: list[str] | None = None,
    scenarios: list[EvaluationScenario] | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Run the full Cartesian product of policies, scenarios, and seeds."""
    policies = policies or ["rule_only", "hybrid"]
    scenarios = scenarios or build_default_scenarios()
    results: list[dict[str, Any]] = []
    for policy in policies:
        for scenario in scenarios:
            for index in range(runs):
                results.append(run_single_evaluation(policy, scenario, seed + index))

    grouped: dict[str, dict[str, Any]] = {}
    for policy in policies:
        policy_runs = [run for run in results if run["policy"] == policy]
        grouped[policy] = {
            "overall": _aggregate_runs(policy_runs),
            "by_scenario": {
                scenario.name: _aggregate_runs([run for run in policy_runs if run["scenario"] == scenario.name])
                for scenario in scenarios
            },
        }

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "seed": seed,
        "runs_per_scenario": runs,
        "policies": policies,
        "scenarios": [scenario.name for scenario in scenarios],
        "summary": grouped,
        "runs": results,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Agent Evaluation Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Seed: {report['seed']}",
        f"- Runs per scenario: {report['runs_per_scenario']}",
        f"- Scenarios: {', '.join(report['scenarios'])}",
        "",
        "## Policy Summary",
        "",
        "| Policy | Runs | Red win | Blue win | Draw | Avg turns | Avg task completion | Avg invalid actions |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy, payload in report["summary"].items():
        overall = payload["overall"]
        lines.append(
            "| {policy} | {runs} | {red:.1%} | {blue:.1%} | {draw:.1%} | {turns:.2f} | {task:.1%} | {invalid:.1%} |".format(
                policy=policy,
                runs=overall["runs"],
                red=overall["red_win_rate"],
                blue=overall["blue_win_rate"],
                draw=overall["draw_rate"],
                turns=overall["avg_turns"],
                task=overall["avg_task_completion_rate"],
                invalid=overall["avg_invalid_action_rate"],
            )
        )
    lines.extend(["", "## Scenario Breakdown", ""])
    for policy, payload in report["summary"].items():
        lines.extend([f"### {policy}", ""])
        lines.append("| Scenario | Runs | Red win | Avg red score | Avg blue score | Avg scout reports used |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for scenario, metrics in payload["by_scenario"].items():
            lines.append(
                "| {scenario} | {runs} | {red:.1%} | {red_score:.3f} | {blue_score:.3f} | {reports:.2f} |".format(
                    scenario=scenario,
                    runs=metrics["runs"],
                    red=metrics["red_win_rate"],
                    red_score=metrics["avg_red_score"],
                    blue_score=metrics["avg_blue_score"],
                    reports=metrics["avg_scout_reports_used"],
                )
            )
        lines.append("")
    return "\n".join(lines)


def write_reports(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    """Write both machine-readable JSON and resume-friendly Markdown reports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "eval_latest.json"
    md_path = output_dir / "eval_latest.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic multi-agent battle policy evaluations.")
    parser.add_argument("--runs", type=int, default=20, help="Number of runs per scenario and policy.")
    parser.add_argument("--seed", type=int, default=42, help="Base random seed.")
    parser.add_argument("--policies", default="rule_only,hybrid", help="Comma-separated policies: rule_only,hybrid.")
    parser.add_argument("--output-dir", default="reports", help="Directory for JSON and Markdown reports.")
    args = parser.parse_args()

    policies = [item.strip() for item in args.policies.split(",") if item.strip()]
    report = run_evaluation(runs=args.runs, policies=policies, seed=args.seed)
    json_path, md_path = write_reports(report, Path(args.output_dir))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
