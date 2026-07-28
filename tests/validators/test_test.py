from probe.validators.test import TestValidator
from probe.validators.base import Category

SUREFIRE = '''<testsuite name="com.x.FooTest" tests="2" failures="1" errors="0" skipped="0">
<testcase name="testA" classname="com.x.FooTest" time="0.1"/>
<testcase name="testB" classname="com.x.FooTest" time="0.2">
<failure type="AssertionError" message="expected [1] but was [2]">expected [1] but was [2]
	at com.x.FooTest.testB(FooTest.java:12)</failure>
</testcase></testsuite>'''


def test_parses_failure(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    d = tmp_path / "target" / "surefire-reports"
    d.mkdir(parents=True)
    (d / "TEST-com.x.FooTest.xml").write_text(SUREFIRE)
    v = TestValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    fails = [f for f in r.failures if f.category == Category.TEST_FAILURE]
    assert len(fails) == 1
    assert fails[0].line == 12
    assert fails[0].file.endswith("FooTest.java")
    assert r.summary.get("TEST_FAILURE") == 1
    assert r.per_validator_status.get("test") == "FAIL"


def test_error_category(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    xml = '''<testsuite name="com.x.BarTest" tests="1" failures="0" errors="1" skipped="0">
<testcase name="testC" classname="com.x.BarTest"><error type="NullPointerException">NPE
	at com.x.BarTest.testC(BarTest.java:7)</error></testcase></testsuite>'''
    d = tmp_path / "target" / "surefire-reports"
    d.mkdir(parents=True)
    (d / "TEST-com.x.BarTest.xml").write_text(xml)
    v = TestValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert any(f.category == Category.TEST_ERROR for f in r.failures)


def test_all_pass(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    d = tmp_path / "target" / "surefire-reports"
    d.mkdir(parents=True)
    (d / "TEST-com.x.OkTest.xml").write_text(
        '<testsuite name="OkTest" tests="1"><testcase name="t" classname="OkTest"/></testsuite>'
    )
    v = TestValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("test") == "PASS"
    assert r.failures == []


def test_skipped_is_missing(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    d = tmp_path / "target" / "surefire-reports"
    d.mkdir(parents=True)
    (d / "TEST-com.x.SkTest.xml").write_text(
        '<testsuite name="SkTest" tests="1" skipped="1"><testcase name="t" classname="SkTest"><skipped/></testcase></testsuite>'
    )
    v = TestValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert any(f.category == Category.TEST_MISSING for f in r.failures)


def test_no_pom_returns_specific_error(tmp_path):
    """When no pom.xml exists, return BUILD_CONFIG_ERROR instead of
    letting Maven fail with a cryptic 'no POM' message."""
    (tmp_path / "README.md").write_text("not a maven project")
    v = TestValidator(runner=lambda cmd, cwd: (1, "", "no POM"))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("test") == "FAIL"
    assert r.failures[0].category == Category.BUILD_CONFIG_ERROR
    assert "pom.xml" in r.failures[0].message.lower()


def test_pom_in_subdir_finds_surefire(tmp_path):
    """When pom.xml is in a subdirectory, run Maven there and find
    surefire reports under subdir/target/surefire-reports."""
    sub = tmp_path / "my-module"
    sub.mkdir()
    (sub / "pom.xml").write_text("<project/>")
    d = sub / "target" / "surefire-reports"
    d.mkdir(parents=True)
    (d / "TEST-com.x.FooTest.xml").write_text(SUREFIRE)
    v = TestValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("test") == "FAIL"
    assert any(f.category == Category.TEST_FAILURE for f in r.failures)
