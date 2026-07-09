from probe.validators.base import Failure, FailureReport, signature, Category


def test_signature_stable_regardless_of_order():
    f1 = Failure(
        validator="test",
        severity="error",
        file="A.java",
        line=3,
        category=Category.TEST_FAILURE,
        message="x",
        raw="",
        hint="h",
    )
    f2 = Failure(
        validator="test",
        severity="error",
        file="B.java",
        line=4,
        category=Category.COMPILE_SYNTAX,
        message="y",
        raw="",
        hint="h",
    )
    assert signature([f1, f2]) == signature([f2, f1])


def test_empty_report_passes():
    r = FailureReport(
        per_validator_status={}, failures=[], signature=signature([]), summary={}
    )
    assert r.failures == []


def test_signature_changes_with_content():
    f1 = Failure(
        validator="test",
        severity="error",
        file="A.java",
        line=3,
        category=Category.TEST_FAILURE,
        message="x",
        raw="",
        hint="h",
    )
    f2 = Failure(
        validator="test",
        severity="error",
        file="A.java",
        line=3,
        category=Category.TEST_FAILURE,
        message="y",
        raw="",
        hint="h",
    )
    assert signature([f1]) != signature([f2])


def test_category_enum_count():
    assert len(Category) == 10
