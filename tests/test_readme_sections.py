def test_readme_has_required_sections():
    t = open("README.md", encoding="utf-8").read()
    for h in ["## 简介", "## 安装", "## 运行", "## 分发", "## 目录结构", "## 安全边界"]:
        assert h in t, f"missing section {h}"


def test_readme_has_docker_run():
    assert "docker run" in open("README.md", encoding="utf-8").read()


def test_readme_has_make_test():
    assert "make test" in open("README.md", encoding="utf-8").read()


def test_env_example_no_real_key():
    t = open(".env.example", encoding="utf-8").read()
    assert "sk-" not in t  # 占位, 无真实 key
    assert "LLM_API_KEY" in t
    assert "LLM_BASE_URL" in t


def test_fly_toml_exists():
    t = open("fly.toml", encoding="utf-8").read()
    assert "app" in t and "8000" in t
