import os
import subprocess
import sys
from pathlib import Path


def run_pre_commit(*arguments: str) -> int:
    project_root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.setdefault(
        "PRE_COMMIT_HOME",
        str(project_root / ".pre-commit-cache"),
    )
    command = [sys.executable, "-m", "pre_commit", *arguments]
    return subprocess.run(
        command,
        cwd=project_root,
        env=environment,
        check=False,
    ).returncode


def install() -> int:
    return run_pre_commit("install")


def run_all() -> int:
    return run_pre_commit("run", "--all-files")
