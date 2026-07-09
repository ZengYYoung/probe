from probe.tools.shell import RunShell


def test_shell_runs_and_captures(tmp_repo):
    r = RunShell(tmp_repo, timeout=10).run({"command": "echo hello"})
    assert r.ok and r.stdout.strip() == "hello" and r.exit_code == 0


def test_shell_nonzero_exit(tmp_repo):
    r = RunShell(tmp_repo, timeout=10).run({"command": "ls /nonexistent_dir_xyz"})
    assert not r.ok and r.exit_code != 0


def test_shell_timeout(tmp_repo):
    r = RunShell(tmp_repo, timeout=1).run({"command": "sleep 5"})
    assert not r.ok and r.meta.get("timeout") is True


def test_shell_cwd_relative(tmp_repo):
    (tmp_repo / "sub").mkdir()
    r = RunShell(tmp_repo, timeout=10).run({"command": "pwd", "cwd": "sub"})
    assert "sub" in r.stdout
