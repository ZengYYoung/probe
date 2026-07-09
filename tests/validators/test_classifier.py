from probe.validators.classifier import classify, classify_report
from probe.validators.base import Failure, FailureReport, Category, signature


def test_cannot_find_symbol_compile():
    f = Failure(
        validator="compile",
        severity="error",
        file="A",
        line=1,
        category=Category.UNKNOWN,
        message="cannot find symbol",
        raw="",
        hint="",
    )
    assert classify(f)[0] == Category.COMPILE_MISSING_SYMBOL


def test_assertion_failure_uses_validator_field():
    f = Failure(
        validator="test",
        severity="error",
        file="A",
        line=1,
        category=Category.UNKNOWN,
        message="expected [1] but was [2]",
        raw="",
        hint="",
    )
    assert classify(f)[0] == Category.TEST_FAILURE


def test_validator_field_disambiguates_same_text():
    fc = Failure(
        validator="compile",
        severity="error",
        file="A",
        line=1,
        category=Category.UNKNOWN,
        message="expected ;",
        raw="",
        hint="",
    )
    ft = Failure(
        validator="test",
        severity="error",
        file="A",
        line=1,
        category=Category.UNKNOWN,
        message="expected",
        raw="",
        hint="",
    )
    assert classify(fc)[0] != Category.TEST_FAILURE
    assert classify(ft)[0] in (Category.TEST_FAILURE, Category.TEST_ERROR, Category.UNKNOWN)


def test_specific_pattern_beats_generic():
    f = Failure(
        validator="test",
        severity="error",
        file="A",
        line=1,
        category=Category.UNKNOWN,
        message="expected [1] but was [2]",
        raw="",
        hint="",
    )
    assert classify(f)[0] == Category.TEST_FAILURE


def test_unknown_stays_unknown():
    f = Failure(
        validator="x",
        severity="error",
        file="A",
        line=1,
        category=Category.UNKNOWN,
        message="weird stuff",
        raw="",
        hint="",
    )
    assert classify(f)[0] == Category.UNKNOWN


def test_classify_report_does_not_mutate_input():
    f = Failure(
        validator="compile",
        severity="error",
        file="A",
        line=1,
        category=Category.UNKNOWN,
        message="cannot find symbol",
        raw="",
        hint="",
    )
    report = FailureReport(
        per_validator_status={"compile": "FAIL"},
        failures=[f],
        signature="old",
        summary={},
    )
    orig_sig = report.signature
    orig_cat = report.failures[0].category
    updated = classify_report(report)
    assert report.signature == orig_sig
    assert report.failures[0].category == orig_cat
    assert updated is not report
    assert updated.failures[0].category == Category.COMPILE_MISSING_SYMBOL
    assert updated.signature == signature(updated.failures)
