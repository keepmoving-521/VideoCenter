from pathlib import Path

import yaml


def load_config() -> dict:
    project_root = Path(__file__).resolve().parents[1]
    with (project_root / ".pre-commit-config.yaml").open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_precommit_config_contains_repository_hygiene_hooks():
    config = load_config()
    hook_ids = {hook["id"] for repository in config["repos"] for hook in repository["hooks"]}

    assert {
        "trailing-whitespace",
        "end-of-file-fixer",
        "check-yaml",
        "check-toml",
        "check-merge-conflict",
        "check-added-large-files",
    } <= hook_ids


def test_precommit_config_contains_ruff_hooks():
    config = load_config()
    hook_ids = {hook["id"] for repository in config["repos"] for hook in repository["hooks"]}

    assert {"ruff-check", "ruff-format"} <= hook_ids
