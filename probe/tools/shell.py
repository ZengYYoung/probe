"""RunShell tool: execute a shell command inside the repo root."""

from __future__ import annotations

import subprocess
from pathlib import Path

from probe.tools.base import Tool, ToolResult, safe_path


class RunShell(Tool):
    """Run a shell command in ``repo_root`` and capture its output."""

    def __init__(self, repo_root: Path, timeout: int = 600) -> None:
        self.repo_root = Path(repo_root)
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "shell"

    def run(self, params: dict) -> ToolResult:
        command = params["command"]
        cwd_rel = params.get("cwd")
        if cwd_rel:
            cwd = safe_path(self.repo_root, cwd_rel)
        else:
            cwd = self.repo_root.resolve()

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                ok=False,
                stdout="",
                stderr="timeout",
                exit_code=-1,
                meta={"timeout": True},
            )

        return ToolResult(
            ok=(proc.returncode == 0),
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
        )
