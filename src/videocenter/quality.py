import subprocess
import sys

CHECK_PATHS = ("src", "tests", "migrations")


def run_ruff(*arguments: str) -> int:
    command = [sys.executable, "-m", "ruff", *arguments, *CHECK_PATHS]
    return subprocess.run(command, check=False).returncode


def main() -> int:
    checks = (
        ("Ruff lint", ("check",)),
        ("Ruff format", ("format", "--check")),
    )
    for label, arguments in checks:
        print(f"==> {label}", flush=True)
        result = run_ruff(*arguments)
        if result != 0:
            return result
    print("All Ruff checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
