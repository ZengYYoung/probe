from probe.validators.lint import LintValidator
from probe.validators.base import Category

CS = '''<?xml version="1.0"?><checkstyle version="8.0">
<file name="/src/Main.java"><error line="3" column="5" severity="error" message="Missing Javadoc" source="JavadocMethod"/></file>
<file name="/src/Other.java"><error line="10" severity="warning" message="Unused import" source="UnusedImports"/></file>
</checkstyle>'''


def test_parses_violation(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    d = tmp_path / "target"
    d.mkdir()
    (d / "checkstyle-result.xml").write_text(CS)
    v = LintValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert r.failures[0].category == Category.LINT_VIOLATION
    assert r.failures[0].line == 3 and "JavadocMethod" in r.failures[0].raw
    assert any(f.line == 10 for f in r.failures)
    assert r.per_validator_status.get("lint") == "FAIL"


def test_clean_lint(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    d = tmp_path / "target"
    d.mkdir()
    (d / "checkstyle-result.xml").write_text(
        '<?xml version="1.0"?><checkstyle version="8.0"></checkstyle>'
    )
    v = LintValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("lint") == "PASS"
    assert r.failures == []


def test_no_report_file(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    v = LintValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("lint") == "UNAVAILABLE"


def test_no_pom_returns_specific_error(tmp_path):
    """When no pom.xml exists, return BUILD_CONFIG_ERROR instead of
    letting Maven fail with a cryptic 'no POM' message."""
    (tmp_path / "README.md").write_text("not a maven project")
    v = LintValidator(runner=lambda cmd, cwd: (1, "", "no POM"))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("lint") == "FAIL"
    assert r.failures[0].category == Category.BUILD_CONFIG_ERROR
    assert "pom.xml" in r.failures[0].message.lower()


def test_pom_in_subdir_finds_checkstyle(tmp_path):
    """When pom.xml is in a subdirectory, run Maven there and find
    checkstyle result under subdir/target/checkstyle-result.xml."""
    sub = tmp_path / "my-module"
    sub.mkdir()
    (sub / "pom.xml").write_text("<project/>")
    d = sub / "target"
    d.mkdir()
    (d / "checkstyle-result.xml").write_text(
        '<?xml version="1.0"?><checkstyle version="8.0"></checkstyle>'
    )
    v = LintValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("lint") == "PASS"
    assert r.failures == []
