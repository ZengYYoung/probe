from probe.report.renderer import render_markdown, render_json
from probe.validators.base import FailureReport, Failure, Category


def _rep():
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
    return FailureReport(
        per_validator_status={"test": "FAIL"},
        failures=[f],
        signature="s",
        summary={"TEST_FAILURE": 1},
    )


def test_md_lists_failure_with_hint():
    md = render_markdown(_rep(), affected={"affected_files": ["A.java"], "tests_to_run": []})
    assert "A.java:5" in md
    assert "TEST_FAILURE" in md
    assert "check assertion" in md


def test_md_includes_affected():
    md = render_markdown(
        _rep(),
        affected={"affected_files": ["A.java", "B.java"], "tests_to_run": ["FooTest"]},
    )
    assert "A.java" in md and "B.java" in md and "FooTest" in md


def test_json_structure():
    j = render_json(_rep(), affected={"affected_files": ["A.java"], "tests_to_run": []})
    assert j["failures"][0]["file"] == "A.java"
    assert j["failures"][0]["category"] == "TEST_FAILURE"
    assert j["summary"]["TEST_FAILURE"] == 1
    assert j["affected"]["affected_files"] == ["A.java"]


def test_md_all_pass():
    r = FailureReport(
        per_validator_status={"compile": "PASS", "test": "PASS", "lint": "PASS"},
        failures=[],
        signature="ok",
        summary={},
    )
    md = render_markdown(r)
    assert "PASS" in md or "pass" in md.lower()
