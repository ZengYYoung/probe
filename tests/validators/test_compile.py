from pathlib import Path

from probe.validators.compile import CompileValidator
from probe.validators.base import Category


def test_parses_javac_errors():
    out = ("[ERROR] /src/Main.java:[5,1] error: ';' expected\n"
           "[ERROR] /src/Other.java:[9,1] error: cannot find symbol\n"
           "[ERROR] /src/Big.java:[12,1] error: cannot find symbol\n")
    v = CompileValidator(runner=lambda cmd, cwd: (1, out, ""))
    r = v.run(repo="/repo")
    cats = {f.category for f in r.failures}
    assert Category.COMPILE_SYNTAX in cats
    assert Category.COMPILE_MISSING_SYMBOL in cats
    files = {f.file for f in r.failures}
    assert any(f.endswith("Main.java") for f in files)
    assert any(f.endswith("Other.java") for f in files)
    assert r.per_validator_status.get("compile") == "FAIL"


def test_clean_compile_passes():
    v = CompileValidator(runner=lambda cmd, cwd: (0, "", ""))
    r = v.run(repo="/repo")
    assert r.per_validator_status.get("compile") == "PASS"
    assert r.failures == []


def test_runner_unavailable():
    def boom(cmd, cwd):
        raise RuntimeError("mvn not found")

    v = CompileValidator(runner=boom)
    r = v.run(repo="/repo")
    assert r.per_validator_status.get("compile") == "UNAVAILABLE"


def test_no_pom_returns_specific_error(tmp_path: Path):
    """When no pom.xml exists, return a specific BUILD_CONFIG_ERROR
    instead of letting Maven fail with a cryptic 'no POM' message."""
    (tmp_path / "README.md").write_text("not a maven project")
    v = CompileValidator(runner=lambda cmd, cwd: (1, "", "no POM"))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("compile") == "FAIL"
    assert len(r.failures) == 1
    f = r.failures[0]
    assert f.category == Category.BUILD_CONFIG_ERROR
    assert "pom.xml" in f.message.lower()
    assert f.hint  # non-empty, actionable hint


def test_gradle_project_returns_specific_error(tmp_path: Path):
    """When build.gradle exists but no pom.xml, report Gradle not supported."""
    (tmp_path / "build.gradle").write_text("apply plugin: 'java'")
    v = CompileValidator(runner=lambda cmd, cwd: (1, "", "no POM"))
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("compile") == "FAIL"
    f = r.failures[0]
    assert f.category == Category.BUILD_CONFIG_ERROR
    assert "gradle" in f.message.lower()


def test_pom_in_subdir_uses_subdir_as_cwd(tmp_path: Path):
    """When pom.xml is in a subdirectory, run Maven there, not at repo root."""
    sub = tmp_path / "my-module"
    sub.mkdir()
    (sub / "pom.xml").write_text("<project/>")
    seen_cwd = []
    v = CompileValidator(
        runner=lambda cmd, cwd: (seen_cwd.append(cwd), (0, "", ""))[-1]
    )
    r = v.run(repo=str(tmp_path))
    assert r.per_validator_status.get("compile") == "PASS"
    assert seen_cwd == [str(sub)]
