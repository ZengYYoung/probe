import yaml, os
def _ci(): return yaml.safe_load(open(".gitlab-ci.yml"))
def test_ci_has_unit_test_job():
    ci = _ci()
    assert "unit-test" in ci
    assert "pytest" in str(ci["unit-test"]["script"])
def test_ci_unit_test_skips_integration():
    ci = _ci()
    assert "-m 'not integration'" in str(ci["unit-test"]["script"])
def test_ci_has_build_image_job():
    ci = _ci()
    assert "build-image" in ci
    assert "docker build" in str(ci["build-image"]["script"])
def test_dockerfile_installs_deps_and_runs_web():
    df = open("Dockerfile").read()
    assert "python" in df.lower()
    assert "default-jdk" in df or "openjdk" in df.lower() or "jdk" in df.lower()
    assert "maven" in df.lower()
    assert "graphviz" in df.lower()
    assert "uvicorn" in df.lower()
def test_dockerignore_excludes_secrets():
    di = open(".dockerignore").read()
    assert ".env" in di
    assert ".git" in di
