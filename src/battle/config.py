import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_project_env() -> dict[str, str]:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass
class BattleConfig:
    grid_size: int = 8
    max_turns: int = 40
    api_key: str | None = None
    api_base_url: str = "https://api.siliconflow.cn/v1"
    model: str = "Qwen/Qwen2.5-7B-Instruct"
    log_dir: str = "outputs/confrontation_logs/"

    def __post_init__(self):
        project_env = load_project_env()
        self.api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("SILICONFLOW_API_KEY")
            or project_env.get("OPENAI_API_KEY")
            or project_env.get("SILICONFLOW_API_KEY")
            or None
        )
        self.api_base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("SILICONFLOW_BASE_URL")
            or project_env.get("OPENAI_BASE_URL")
            or project_env.get("SILICONFLOW_BASE_URL")
            or self.api_base_url
        )
        self.model = (
            os.getenv("OPENAI_MODEL")
            or os.getenv("SILICONFLOW_MODEL")
            or project_env.get("OPENAI_MODEL")
            or project_env.get("SILICONFLOW_MODEL")
            or self.model
        )
        os.makedirs(self.log_dir, exist_ok=True)


config = BattleConfig()
