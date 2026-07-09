import pytest
from probe.tools.base import safe_path, Tool, ToolResult
def test_safe_path_blocks_traversal(tmp_path):
    with pytest.raises(PermissionError):
        safe_path(tmp_path, "../../etc/passwd")
def test_safe_path_allows_inner(tmp_path):
    p = safe_path(tmp_path, "src/Main.java")
    assert str(p).startswith(str(tmp_path))
def test_safe_path_normalizes(tmp_path):
    (tmp_path/"src").mkdir()
    p = safe_path(tmp_path, "src/../src/./Main.java")
    assert p.is_relative_to(tmp_path)
def test_toolresult_defaults():
    r = ToolResult(ok=True)
    assert r.stdout == "" and r.exit_code is None and r.meta == {}
