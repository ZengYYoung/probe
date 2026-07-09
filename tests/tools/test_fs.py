import pytest
from probe.tools.fs import ReadFile, WriteFile, PatchFile, ListFiles
def test_write_then_read(tmp_repo):
    w = WriteFile(tmp_repo); r = ReadFile(tmp_repo)
    assert w.run({"path":"a.txt","content":"hi"}).ok
    assert r.run({"path":"a.txt"}).stdout == "hi"
def test_patch_replaces(tmp_repo):
    WriteFile(tmp_repo).run({"path":"a.txt","content":"a\nb\nc\n"})
    pr = PatchFile(tmp_repo).run({"path":"a.txt","old":"b","new":"B"})
    assert pr.ok
    assert "B" in ReadFile(tmp_repo).run({"path":"a.txt"}).stdout
def test_patch_old_not_found(tmp_repo):
    WriteFile(tmp_repo).run({"path":"a.txt","content":"x"})
    pr = PatchFile(tmp_repo).run({"path":"a.txt","old":"zzz","new":"y"})
    assert not pr.ok
def test_read_outside_repo_blocked(tmp_repo):
    with pytest.raises(PermissionError): ReadFile(tmp_repo).run({"path":"../etc/passwd"})
def test_listfiles_lists_java(tmp_repo):
    WriteFile(tmp_repo).run({"path":"src/Main.java","content":"class Main{}"})
    WriteFile(tmp_repo).run({"path":"src/Helper.java","content":"class Helper{}"})
    WriteFile(tmp_repo).run({"path":"README.txt","content":"x"})
    out = ListFiles(tmp_repo).run({"path":"src"}).stdout
    assert "Main.java" in out and "Helper.java" in out
    assert "README.txt" not in out
