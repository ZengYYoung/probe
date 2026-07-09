from probe.memory.store import Memory


def test_append_and_recent(tmp_repo):
    m = Memory(tmp_repo)
    m.append_decision({"iter": 1, "sig": "abc", "action": "CONTINUE"})
    m.append_decision({"iter": 2, "sig": "abc", "action": "STOP"})
    recent = m.recent(2)
    assert len(recent) == 2
    assert recent[1]["iter"] == 2


def test_missing_file_degrades(tmp_repo):
    m = Memory(tmp_repo)
    assert m.recent(5) == []  # 不阻断


def test_conventions(tmp_repo):
    m = Memory(tmp_repo)
    m.set_convention("tests_dir", "src/test/java")
    assert m.get_conventions()["tests_dir"] == "src/test/java"


def test_persists_across_instances(tmp_repo):
    m = Memory(tmp_repo)
    m.append_decision({"iter": 1, "sig": "x", "action": "CONTINUE"})
    m2 = Memory(tmp_repo)
    assert len(m2.recent(5)) == 1


def test_writes_to_probe_dir(tmp_repo):
    m = Memory(tmp_repo)
    m.append_decision({"iter": 1, "sig": "x", "action": "CONTINUE"})
    assert (tmp_repo / ".probe" / "memory.json").exists()
