from probe.validators.lint import LintValidator
from probe.validators.base import Category

CS = '''<?xml version="1.0"?><checkstyle version="8.0">
<file name="/src/Main.java"><error line="3" column="5" severity="error" message="Missing Javadoc" source="JavadocMethod"/></file>
<file name="/src/Other.java"><error line="10" severity="warning" message="Unused import" source="UnusedImports"/></file>
</checkstyle>'''


def test_parses_violation(tmp_path):
    d = tmp_path / "target"
    d.mkdir()
    (d / "checkstyle-result.xml").write_text(CS)
    v = LintValidator(runner=lambda cmd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert r.failures[0].category == Category.LINT_VIOLATION
    assert r.failures[0].line == 3 and "JavadocMethod" in r.failures[0].raw
    assert any(f.line == 10 for f in r.failures)
    assert r.per_validator_status.get("lint") == "FAIL"


def test_clean_lint(tmp_path):
    d = tmp_path / "target"
    d.mkdir()
    (d / "checkstyle-result.xml").write_text(
        '<?xml version="1.0"?><checkstyle version="8.0"></checkstyle>'
    )
    v = LintValidator(runner=lambda cmd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("lint") == "PASS"
    assert r.failures == []


def test_no_report_file(tmp_path):
    v = LintValidator(runner=lambda cmd: (0, "", ""))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("lint") == "UNAVAILABLE"
