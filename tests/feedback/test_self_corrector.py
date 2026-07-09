from probe.feedback.self_corrector import SelfCorrector, Decision
from probe.validators.base import FailureReport, Failure, Category
from probe.config import Config


def _cfg():
    return Config.load(None, env={})  # K=3


def _rep(sig, fails=None):
    return FailureReport(
        per_validator_status={"compile": "FAIL"} if fails is not None else {"compile": "PASS", "test": "PASS", "lint": "PASS"},
        failures=fails or [],
        signature=sig,
        summary={},
    )


def test_success_when_all_pass():
    r = FailureReport(
        per_validator_status={"compile": "PASS", "test": "PASS", "lint": "PASS"},
        failures=[],
        signature="s",
        summary={},
    )
    d = SelfCorrector(_cfg()).decide(r, history=[], budget_remaining=1000)
    assert d.action == "STOP" and d.reason == "SUCCESS"


def test_no_progress_after_K_rounds():
    s = SelfCorrector(_cfg())
    r = _rep(
        "same",
        [
            Failure(
                validator="compile",
                severity="error",
                file="A",
                line=1,
                category=Category.COMPILE_SYNTAX,
                message="e",
                raw="",
                hint="",
            )
        ],
    )
    assert s.decide(r, ["same"], 1000).action == "CONTINUE"
    assert s.decide(r, ["same", "same"], 1000).action == "CONTINUE"
    d3 = s.decide(r, ["same", "same", "same"], 1000)
    assert d3.action == "STOP" and d3.reason == "BLOCKED_NO_PROGRESS"


def test_budget_exhausted():
    r = _rep(
        "x",
        [
            Failure(
                validator="compile",
                severity="error",
                file="A",
                line=1,
                category=Category.COMPILE_SYNTAX,
                message="e",
                raw="",
                hint="",
            )
        ],
    )
    d = SelfCorrector(_cfg()).decide(r, history=[], budget_remaining=0)
    assert d.action == "STOP" and d.reason == "STOPPED_BUDGET"


def test_continue_and_context_fragment():
    f = Failure(
        validator="test",
        severity="error",
        file="A.java",
        line=5,
        category=Category.TEST_FAILURE,
        message="expected [1] but was [2]",
        raw="",
        hint="check assertion",
    )
    r = FailureReport(
        per_validator_status={"test": "FAIL"},
        failures=[f],
        signature="s1",
        summary={"TEST_FAILURE": 1},
    )
    d = SelfCorrector(_cfg()).decide(r, history=["old"], budget_remaining=500)
    assert d.action == "CONTINUE"
    assert "A.java:5" in d.context_fragment
    assert "TEST_FAILURE" in d.context_fragment
    assert "check assertion" in d.context_fragment


def test_progress_resets_no_progress_counter():
    # 签名变化→不触发 BLOCKED
    s = SelfCorrector(_cfg())
    r1 = _rep(
        "sig1",
        [
            Failure(
                validator="compile",
                severity="error",
                file="A",
                line=1,
                category=Category.COMPILE_SYNTAX,
                message="e",
                raw="",
                hint="",
            )
        ],
    )
    r2 = _rep(
        "sig2",
        [
            Failure(
                validator="compile",
                severity="error",
                file="A",
                line=1,
                category=Category.COMPILE_SYNTAX,
                message="f",
                raw="",
                hint="",
            )
        ],
    )
    assert s.decide(r1, ["sig1", "sig1"], 1000).action == "CONTINUE"  # 只2轮同签名,未到K=3
    # sig1 出现2次 + sig2 1次 → sig1 count=2 <3, 继续
