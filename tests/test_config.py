from pathlib import Path

from probe.config import Config


def test_config_defaults_and_override():
    cfg = Config.load(Path("probe.yaml.example"), env={})
    assert cfg.budgets.max_iterations == 10
    assert cfg.no_progress_rounds == 3
    assert "rm -rf" in cfg.guardrails.dangerous_patterns
    cfg2 = Config.load(Path("probe.yaml.example"), env={"PROBE_MAX_ITERATIONS": "5"})
    assert cfg2.budgets.max_iterations == 5


def test_config_load_none_path_returns_defaults():
    """path=None 入口（T18/T23 使用）：不读文件，全默认。"""
    cfg = Config.load(None, env={})
    assert cfg.budgets.max_iterations == 10
    assert cfg.budgets.max_shell_seconds == 600
    assert cfg.budgets.max_tokens == 50000
    assert cfg.no_progress_rounds == 3
    assert cfg.validators.compile is True
    assert cfg.validators.test is True
    assert cfg.validators.lint is True
    assert cfg.llm.model == "glm-5.2"
    assert cfg.llm.temperature == 0.2
    assert "git push --force" in cfg.guardrails.dangerous_patterns
    assert cfg.guardrails.allowed_paths == []


def test_config_env_overrides():
    cfg = Config.load(None, env={
        "PROBE_MAX_ITERATIONS": "7",
        "PROBE_NO_PROGRESS_ROUNDS": "5",
        "PROBE_LLM_MODEL": "gpt-4o",
    })
    assert cfg.budgets.max_iterations == 7
    assert cfg.no_progress_rounds == 5
    assert cfg.llm.model == "gpt-4o"
