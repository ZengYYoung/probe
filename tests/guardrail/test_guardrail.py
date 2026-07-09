from probe.guardrail.guardrail import guardrail, Verdict
from probe.llm.base import Action
from probe.config import Config


def _cfg():
    return Config.load(None, env={})


def test_blocks_rm_rf():
    v = guardrail(Action(type="shell", command="rm -rf /"), _cfg())
    assert not v.allow and "rm -rf" in v.reason


def test_blocks_git_push_force():
    v = guardrail(Action(type="shell", command="git push --force origin main"), _cfg())
    assert not v.allow


def test_blocks_mvn_deploy():
    v = guardrail(Action(type="shell", command="mvn deploy"), _cfg())
    assert not v.allow


def test_allows_ls():
    assert guardrail(Action(type="shell", command="ls -la"), _cfg()).allow


def test_blocks_path_escape():
    v = guardrail(Action(type="write", path="../../etc/passwd", params={}), _cfg())
    assert not v.allow


def test_allows_inner_path():
    assert guardrail(Action(type="write", path="src/A.java", params={}), _cfg()).allow


def test_unknown_action_blocked():
    v = guardrail(Action(type="teleport", params={}), _cfg())
    assert not v.allow
