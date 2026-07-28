"""Tests for probe.validators.project — Maven root auto-discovery.

Covers the scenario where an uploaded zip doesn't have pom.xml at the
extracted root (e.g. multi-module project, nested structure, or Gradle
project). The harness must detect this and either use the correct
subdirectory or return an actionable BUILD_CONFIG_ERROR.
"""

import os
from pathlib import Path

from probe.validators.project import find_maven_root


def test_pom_at_root(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project/>")
    (tmp_path / "src").mkdir()
    maven_dir, reason = find_maven_root(str(tmp_path))
    assert maven_dir == str(tmp_path)
    assert reason == "root"


def test_pom_in_subdir(tmp_path: Path):
    sub = tmp_path / "my-module"
    sub.mkdir()
    (sub / "pom.xml").write_text("<project/>")
    maven_dir, reason = find_maven_root(str(tmp_path))
    assert maven_dir == str(sub)
    assert reason == "subdir"


def test_pom_in_nested_subdir(tmp_path: Path):
    deep = tmp_path / "parent" / "child"
    deep.mkdir(parents=True)
    (deep / "pom.xml").write_text("<project/>")
    maven_dir, reason = find_maven_root(str(tmp_path))
    assert maven_dir is not None
    assert maven_dir.endswith(str(Path("parent") / "child"))
    assert reason == "subdir"


def test_gradle_no_pom(tmp_path: Path):
    (tmp_path / "build.gradle").write_text("apply plugin: 'java'")
    maven_dir, reason = find_maven_root(str(tmp_path))
    assert maven_dir is None
    assert reason == "gradle"


def test_no_build_file(tmp_path: Path):
    (tmp_path / "README.md").write_text("hello")
    maven_dir, reason = find_maven_root(str(tmp_path))
    assert maven_dir is None
    assert reason == "none"


def test_nonexistent_path_fallback():
    """When the repo path doesn't exist (e.g. test mode with fake paths),
    fall back to returning the path as-is so the injected runner can handle it.
    """
    maven_dir, reason = find_maven_root("/nonexistent/repo/path")
    assert maven_dir == "/nonexistent/repo/path"
    assert reason == "fallback"


def test_prefers_root_pom_over_subdir(tmp_path: Path):
    """If pom.xml exists at both root and a subdir, prefer root."""
    (tmp_path / "pom.xml").write_text("<project/>")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "pom.xml").write_text("<project/>")
    maven_dir, reason = find_maven_root(str(tmp_path))
    assert maven_dir == str(tmp_path)
    assert reason == "root"
