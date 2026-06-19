from videocenter import hooks


def test_hook_install_command(monkeypatch):
    calls = []

    def fake_run_pre_commit(*arguments):
        calls.append(arguments)
        return 0

    monkeypatch.setattr(hooks, "run_pre_commit", fake_run_pre_commit)

    assert hooks.install() == 0
    assert calls == [("install",)]


def test_hook_run_all_command(monkeypatch):
    calls = []

    def fake_run_pre_commit(*arguments):
        calls.append(arguments)
        return 0

    monkeypatch.setattr(hooks, "run_pre_commit", fake_run_pre_commit)

    assert hooks.run_all() == 0
    assert calls == [("run", "--all-files")]
