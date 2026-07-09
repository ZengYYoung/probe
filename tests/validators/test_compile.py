from probe.validators.compile import CompileValidator
from probe.validators.base import Category


def test_parses_javac_errors():
    out = ("[ERROR] /src/Main.java:[5,1] error: ';' expected\n"
           "[ERROR] /src/Other.java:[9,1] error: cannot find symbol\n"
           "[ERROR] /src/Big.java:[12,1] error: cannot find symbol\n")
    v = CompileValidator(runner=lambda cmd: (1, out, ""))
    r = v.run(repo="/repo")
    cats = {f.category for f in r.failures}
    assert Category.COMPILE_SYNTAX in cats
    assert Category.COMPILE_MISSING_SYMBOL in cats
    files = {f.file for f in r.failures}
    assert any(f.endswith("Main.java") for f in files)
    assert any(f.endswith("Other.java") for f in files)
    assert r.per_validator_status.get("compile") == "FAIL"


def test_clean_compile_passes():
    v = CompileValidator(runner=lambda cmd: (0, "", ""))
    r = v.run(repo="/repo")
    assert r.per_validator_status.get("compile") == "PASS"
    assert r.failures == []


def test_runner_unavailable():
    def boom(cmd):
        raise RuntimeError("mvn not found")

    v = CompileValidator(runner=boom)
    r = v.run(repo="/repo")
    assert r.per_validator_status.get("compile") == "UNAVAILABLE"
