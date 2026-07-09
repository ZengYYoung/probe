import pytest


@pytest.fixture
def tmp_repo(tmp_path):
    """一个空 Java 仓临时目录。"""
    return tmp_path
