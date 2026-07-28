"""Project structure detection — Maven root auto-discovery.

When a user uploads a Java project zip, the extracted directory may not
have ``pom.xml`` at the root (multi-module project, nested zip structure,
or a Gradle project). This module locates the Maven root so validators
run ``mvn`` in the correct directory, or returns an actionable signal
when no Maven project is found.

This is the "check + assist" layer (CLAUDE.md §2.5): the harness detects
the project structure and either adapts or reports a specific, actionable
error — instead of letting Maven fail with a cryptic "no POM" message.
"""

from __future__ import annotations

from pathlib import Path


def find_maven_root(repo: str) -> tuple[str | None, str]:
    """Locate the Maven project root within ``repo``.

    Returns ``(maven_dir, reason)`` where:

    - ``maven_dir``: the directory containing ``pom.xml``, or ``None``
      when no ``pom.xml`` is found anywhere under ``repo``.
    - ``reason``: one of:

      - ``"root"`` — ``pom.xml`` is at ``repo`` root (normal case).
      - ``"subdir"`` — ``pom.xml`` found in a subdirectory; validators
        should use ``maven_dir`` as the working directory.
      - ``"gradle"`` — no ``pom.xml`` but ``build.gradle`` detected
        (Gradle project; SPEC §10 R1 — not deeply supported).
      - ``"none"`` — no build file found at all.
      - ``"fallback"`` — ``repo`` path doesn't exist on disk (test mode
        with fake paths); returns ``repo`` as-is so injected runners
        can handle it.

    Search depth is limited to 3 levels to avoid scanning huge trees.
    Root-level ``pom.xml`` is always preferred over subdirectory matches.
    """
    repo_path = Path(repo)

    # Test mode: path doesn't exist — return as-is so injected runners work.
    if not repo_path.is_dir():
        return repo, "fallback"

    # Prefer root-level pom.xml.
    if (repo_path / "pom.xml").is_file():
        return str(repo_path), "root"

    # Search subdirectories for pom.xml (depth-limited).
    for pom in repo_path.rglob("pom.xml"):
        rel = pom.relative_to(repo_path)
        if len(rel.parts) <= 3:
            return str(pom.parent), "subdir"

    # No pom.xml — check for Gradle.
    if (repo_path / "build.gradle").is_file():
        return None, "gradle"
    for gradle in repo_path.rglob("build.gradle"):
        rel = gradle.relative_to(repo_path)
        if len(rel.parts) <= 3:
            return None, "gradle"

    return None, "none"
