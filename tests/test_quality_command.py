from videocenter import quality


def test_quality_command_runs_lint_and_format_checks(monkeypatch):
    calls = []

    def fake_run_ruff(*arguments):
        calls.append(arguments)
        return 0

    monkeypatch.setattr(quality, "run_ruff", fake_run_ruff)

    assert quality.main() == 0
    assert calls == [
        ("check",),
        ("format", "--check"),
    ]


def test_quality_command_stops_after_first_failure(monkeypatch):
    calls = []

    def fake_run_ruff(*arguments):
        calls.append(arguments)
        return 1

    monkeypatch.setattr(quality, "run_ruff", fake_run_ruff)

    assert quality.main() == 1
    assert calls == [("check",)]
