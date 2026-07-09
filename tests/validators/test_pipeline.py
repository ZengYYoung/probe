from probe.validators.pipeline import ValidatorPipeline
from probe.validators.base import FailureReport, Failure, Category, signature


def test_compile_fail_shortcircuits_test():
    class FakeCompile:
        def run(self, repo, changed_files=None):
            return FailureReport(
                per_validator_status={"compile": "FAIL"},
                failures=[
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
                signature="x",
                summary={"COMPILE_SYNTAX": 1},
            )

    ran = {"test": False, "lint": False}

    class FakeTest:
        def run(self, repo, changed_files=None):
            ran["test"] = True
            return FailureReport(per_validator_status={"test": "PASS"}, failures=[], signature=signature([]), summary={})

    class FakeLint:
        def run(self, repo, changed_files=None):
            ran["lint"] = True
            return FailureReport(per_validator_status={"lint": "PASS"}, failures=[], signature=signature([]), summary={})

    p = ValidatorPipeline(compile_v=FakeCompile(), test_v=FakeTest(), lint_v=FakeLint())
    r = p.run(repo="/r")
    assert ran["test"] is False  # 被短路
    assert ran["lint"] is True  # lint 总跑
    assert r.per_validator_status["compile"] == "FAIL"
    assert r.per_validator_status.get("test") == "SKIPPED"
    assert r.per_validator_status["lint"] == "PASS"


def test_all_pass():
    class FakeV:
        def __init__(self, name):
            self.name = name

        def run(self, repo, changed_files=None):
            return FailureReport(per_validator_status={self.name: "PASS"}, failures=[], signature=signature([]), summary={})

    p = ValidatorPipeline(
        compile_v=FakeV("compile"), test_v=FakeV("test"), lint_v=FakeV("lint")
    )
    r = p.run(repo="/r")
    assert all(v == "PASS" for v in r.per_validator_status.values())
    assert r.failures == []


def test_merges_failures_and_recomputes_signature():
    class FakeV:
        def __init__(self, name, fails):
            self.name = name
            self.fails = fails

        def run(self, repo, changed_files=None):
            return FailureReport(
                per_validator_status={self.name: "FAIL" if self.fails else "PASS"},
                failures=self.fails,
                signature=signature(self.fails),
                summary={},
            )

    tf = [
        Failure(
            validator="test",
            severity="error",
            file="B",
            line=2,
            category=Category.TEST_FAILURE,
            message="t",
            raw="",
            hint="",
        )
    ]
    lf = [
        Failure(
            validator="lint",
            severity="error",
            file="C",
            line=3,
            category=Category.LINT_VIOLATION,
            message="l",
            raw="",
            hint="",
        )
    ]
    # compile PASS（不短路）→ test 与 lint 各带失败，验合并/签名
    p = ValidatorPipeline(
        compile_v=FakeV("compile", []),
        test_v=FakeV("test", tf),
        lint_v=FakeV("lint", lf),
    )
    r = p.run(repo="/r")
    assert len(r.failures) == 2
    assert r.signature == signature(tf + lf)  # 合并后重算
