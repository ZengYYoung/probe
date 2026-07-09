"""Task 26: CLI 子命令单测。

测试直接调 cli 模块的函数（creds_status / init_creds / run_map /
creds_clear）以便于 monkeypatch 与断言；CLI 入口 main() 用 argparse 调这些函数。
"""
import subprocess
import sys

import getpass

from probe import cli


def test_creds_status_masks(monkeypatch, tmp_path, capsys):
    store = cli.CredentialStore(backend="file", store_dir=tmp_path)
    store.set("LLM_API_KEY", "sk-secret-XYZ1234")
    # 调 cli 的 creds_status 函数
    cli.creds_status(store, "LLM_API_KEY")
    out = capsys.readouterr().out
    assert "sk-secret-XYZ1234" not in out
    assert "XYZ1234" in out   # 末尾可见


def test_init_guides_key_entry(monkeypatch, tmp_path):
    inputs = iter(["sk-test-key-abcd"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(inputs))
    store = cli.CredentialStore(backend="file", store_dir=tmp_path)
    cli.init_creds(store)
    assert store.get("LLM_API_KEY") == "sk-test-key-abcd"


def test_map_outputs_dot(monkeypatch, tmp_repo):
    # cli.run_map 给定空仓, 输出含 digraph
    out = cli.run_map(tmp_repo, kind="package")
    assert "digraph" in out


def test_creds_clear(monkeypatch, tmp_path):
    store = cli.CredentialStore(backend="file", store_dir=tmp_path)
    store.set("LLM_API_KEY", "x")
    cli.creds_clear(store, "LLM_API_KEY")
    assert store.get("LLM_API_KEY") is None
