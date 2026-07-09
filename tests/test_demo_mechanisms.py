import demo_mechanisms as dm

def test_demo_guardrail_blocks():
    out = dm.demo_guardrail()
    assert "BLOCKED" in out or "blocked" in out.lower()

def test_demo_feedback_changes_next_action():
    log = dm.demo_feedback_loop()
    # 注入 TEST_FAILURE 后, agent 下一步动作应为 patch(而非 stop)
    assert isinstance(log, list)
    assert any("patch" in str(s).lower() for s in log[1:])

def test_demo_no_progress_blocks():
    out = dm.demo_no_progress()
    assert "BLOCKED_NO_PROGRESS" in out
