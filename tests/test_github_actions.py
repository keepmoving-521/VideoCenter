from pathlib import Path

import yaml


def load_workflow() -> dict:
    project_root = Path(__file__).resolve().parents[1]
    workflow_path = project_root / ".github" / "workflows" / "ci.yml"
    with workflow_path.open(encoding="utf-8") as file:
        return yaml.load(file, Loader=yaml.BaseLoader)


def test_ci_workflow_triggers_on_main_and_pull_requests():
    workflow = load_workflow()
    triggers = workflow["on"]

    assert "main" in triggers["push"]["branches"]
    assert "pull_request" in triggers
    assert "workflow_dispatch" in triggers


def test_ci_workflow_uses_locked_python_environment():
    workflow = load_workflow()
    job = workflow["jobs"]["test"]
    steps = job["steps"]

    assert job["runs-on"] == "ubuntu-latest"
    assert any(step.get("uses") == "actions/setup-python@v6" for step in steps)
    assert any(step.get("uses") == "astral-sh/setup-uv@v8.2.0" for step in steps)
    assert any(step.get("run") == "uv sync --frozen --extra dev" for step in steps)


def test_ci_workflow_runs_quality_migrations_and_tests():
    workflow = load_workflow()
    commands = "\n".join(step["run"] for step in workflow["jobs"]["test"]["steps"] if "run" in step)

    assert "pre-commit run --all-files" in commands
    assert "alembic upgrade head" in commands
    assert "alembic check" in commands
    assert "pytest" in commands
    assert "--cov=videocenter" in commands
