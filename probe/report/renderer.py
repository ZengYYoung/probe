"""Report rendering for FailureReport (Task 24).

Pure rendering, no side effects. Produces Markdown and dict/JSON views of a
:class:`FailureReport`, optionally enriched with an affected-files/tests map
(``AffectedResult``-shaped dict).
"""

from __future__ import annotations

from probe.validators.base import FailureReport


def render_markdown(report: FailureReport, affected: dict | None = None) -> str:
    """Render a human-readable Markdown feasibility report.

    Sections:
      - title ``# 可行性报告``
      - per-validator status line(s)
      - failures table (file:line | category | message | hint)
      - affected-files / tests-to-run section (if ``affected`` provided)
      - "全部通过" note when no failures recorded
    """
    lines: list[str] = ["# 可行性报告", ""]

    # Per-validator status
    if report.per_validator_status:
        status_parts = [f"{k}: {v}" for k, v in report.per_validator_status.items()]
        lines.append("**状态**: " + " | ".join(status_parts))
        lines.append("")

    all_pass = not report.failures and all(
        s == "PASS" for s in report.per_validator_status.values()
    )

    if report.failures:
        lines.append("## 失败列表")
        lines.append("")
        lines.append("| 位置 | 类别 | 消息 | 提示 |")
        lines.append("| --- | --- | --- | --- |")
        for f in report.failures:
            loc = f"{f.file}:{f.line}" if f.line is not None else f.file
            lines.append(
                f"| {loc} | {f.category.value} | {f.message} | {f.hint} |"
            )
        lines.append("")
    elif all_pass:
        lines.append("全部通过")
        lines.append("")

    if affected:
        lines.append("## 影响面")
        lines.append("")
        affected_files = affected.get("affected_files") or []
        if affected_files:
            lines.append("**受影响文件**:")
            for fp in affected_files:
                lines.append(f"- {fp}")
            lines.append("")
        tests_to_run = affected.get("tests_to_run") or []
        if tests_to_run:
            lines.append("**待运行测试**:")
            for t in tests_to_run:
                lines.append(f"- {t}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_json(report: FailureReport, affected: dict | None = None) -> dict:
    """Render a plain dict view of the report for machine consumption."""
    return {
        "per_validator_status": dict(report.per_validator_status),
        "failures": [
            {
                "validator": f.validator,
                "severity": f.severity,
                "file": f.file,
                "line": f.line,
                "category": f.category.value,
                "message": f.message,
                "raw": f.raw,
                "hint": f.hint,
            }
            for f in report.failures
        ],
        "signature": report.signature,
        "summary": dict(report.summary),
        "affected": dict(affected) if affected else {},
    }
