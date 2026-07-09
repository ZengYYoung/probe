"""Probe CLI (Task 26).

argparse-based entry point exposing ``probe init|run|map|creds``.

The subcommands delegate to thin helper functions (``init_creds``,
``creds_status``, ``creds_clear``, ``run_map``, ``run_task``) so they can be
unit-tested directly without spawning a subprocess. Credential secrets are
never echoed: ``creds_status`` prints only the masked form, and ``init_creds``
uses ``getpass.getpass`` for entry.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from probe.credentials import (
    CredentialBackendUnavailable,
    CredentialStore,
    mask,
)
from probe.config import Config
from probe.core.loop import AgentLoop, Task
from probe.core.types import Status
from probe.codemap.builder import build_graph
from probe.codemap.renderer import render_class_dot, render_package_dot
from probe.feedback.self_corrector import SelfCorrector
from probe.llm.openai_compat import OpenAICompatibleClient
from probe.report.renderer import render_markdown
from probe.tools.registry import ToolRegistry
from probe.validators.compile import CompileValidator
from probe.validators.lint import LintValidator
from probe.validators.pipeline import ValidatorPipeline
from probe.validators.test import TestValidator

# Default file-backend store directory (kept under the user's home).
_DEFAULT_STORE_DIR = Path.home() / ".probe"

# Keys the CLI knows how to seed during ``probe init``.
_INIT_KEYS = ("LLM_API_KEY", "LLM_BASE_URL")


# ---------------------------------------------------------------------------
# Store construction
# ---------------------------------------------------------------------------

def _get_store(store_dir: Optional[Path] = None) -> CredentialStore:
    """Return a :class:`CredentialStore`, preferring keychain, falling back to file.

    The file backend lives at ``~/.probe/credentials.json`` (or ``store_dir``
    when provided). Keychain unavailability (no keyring lib / locked) is
    caught and the file backend is used instead.
    """
    try:
        return CredentialStore(backend="keychain")
    except (CredentialBackendUnavailable, Exception):  # noqa: BLE001
        sd = store_dir if store_dir is not None else _DEFAULT_STORE_DIR
        return CredentialStore(backend="file", store_dir=sd)


# ---------------------------------------------------------------------------
# creds subcommand helpers
# ---------------------------------------------------------------------------

def _status_mask(value: str, tail: int = 7) -> str:
    """Status-line mask: first 3 + ``…`` + last ``tail`` chars.

    Longer tail than :func:`probe.credentials.mask` (which shows 4) so a
    user can recognize the credential at a glance while the full plaintext
    remains hidden. Values shorter than ``tail + 3`` collapse to a fully
    masked ``…`` string (never reveals plaintext).
    """
    if value is None:
        return "<not set>"
    if len(value) < tail + 3:
        return "…" * max(1, len(value))
    return f"{value[:3]}…{value[-tail:]}"


def init_creds(store: CredentialStore) -> None:
    """Prompt for ``LLM_API_KEY`` and ``LLM_BASE_URL`` via getpass.

    Empty input (or an exhausted input stream under tests) is skipped,
    leaving any existing value intact. Entry uses getpass so the value is
    never echoed to the terminal or shell history.
    """
    import getpass

    for key in _INIT_KEYS:
        prompt = f"Enter {key} (blank to skip): "
        try:
            value = getpass.getpass(prompt)
        except (EOFError, StopIteration):
            value = ""
        if value:
            store.set(key, value)


def creds_status(store: CredentialStore, key: str) -> None:
    """Print the masked status of ``key``; ``<not set>`` if absent.

    The plaintext value is never printed. Uses a longer-tail mask than
    :meth:`CredentialStore.status` so the credential is recognizable.
    """
    val = store.get(key)
    if val is None:
        print(f"{key}: <not set>")
        return
    print(f"{key}: {_status_mask(val)}")


def creds_update(store: CredentialStore, key: str) -> None:
    """Prompt for a new value for ``key`` via getpass and store it."""
    import getpass

    value = getpass.getpass(f"Enter new value for {key}: ")
    if value:
        store.set(key, value)


def creds_clear(store: CredentialStore, key: str) -> None:
    """Clear ``key`` from the store (idempotent)."""
    store.clear(key)


# ---------------------------------------------------------------------------
# map subcommand helper
# ---------------------------------------------------------------------------

def run_map(
    repo: Path,
    kind: Optional[str] = "package",
    package: Optional[str] = None,
) -> str:
    """Build a CodeGraph for ``repo`` and render DOT.

    - ``kind="package"`` (default): package-level digraph.
    - ``kind="class"``: class-level digraph, optionally filtered by ``package``.
    """
    graph = build_graph(Path(repo))
    if kind == "class":
        return render_class_dot(graph, package=package)
    return render_package_dot(graph)


# ---------------------------------------------------------------------------
# run subcommand helper
# ---------------------------------------------------------------------------

def run_task(
    goal: str,
    repo: str,
    config_path: Optional[str] = None,
) -> None:
    """Assemble a real :class:`AgentLoop` and run ``goal`` over ``repo``.

    Wires:
      - LLM: :class:`OpenAICompatibleClient` built from CredentialStore key
        + base_url.
      - Tools: :meth:`ToolRegistry.for_repo`.
      - Validators: real Compile/Test/Lint pipeline.
      - SelfCorrector with the loaded Config.
    The resulting markdown feasibility report is printed to stdout.
    """
    store = _get_store()
    api_key = store.get("LLM_API_KEY")
    base_url = store.get("LLM_BASE_URL")
    if not api_key:
        print(
            "error: LLM_API_KEY not set. Run `probe init` first.",
            file=sys.stderr,
        )
        sys.exit(2)
    if not base_url:
        print(
            "error: LLM_BASE_URL not set. Run `probe init` first.",
            file=sys.stderr,
        )
        sys.exit(2)

    config = Config.load(Path(config_path) if config_path else None, env=dict(__import__("os").environ))

    llm = OpenAICompatibleClient(
        base_url=base_url,
        api_key=api_key,
        model=config.llm.model,
    )
    registry = ToolRegistry.for_repo(Path(repo))
    pipeline = ValidatorPipeline(
        CompileValidator(),
        TestValidator(),
        LintValidator(),
        config,
    )
    self_corrector = SelfCorrector(config)

    loop = AgentLoop(
        llm=llm,
        registry=registry,
        pipeline=pipeline,
        config=config,
        repo=repo,
        self_corrector=self_corrector,
    )

    task = Task(goal=goal, target_repo=repo)
    result = loop.run(task)

    # Run the pipeline once at the end to produce a final failure report for
    # the markdown rendering (the loop's per-step reports drive correction).
    final_report = result.final_failure_report
    if final_report is None:
        final_report = pipeline.run(repo, changed_files=None)
    print(render_markdown(final_report))
    print(f"\n**status**: {result.status.value}", end="")


# ---------------------------------------------------------------------------
# argparse entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="probe",
        description="Probe coding-agent harness CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    sub.add_parser("init", help="Initialize credentials (LLM_API_KEY, LLM_BASE_URL).")

    # run
    p_run = sub.add_parser("run", help="Run an agent task over a Java repo.")
    p_run.add_argument("--goal", required=True, help="The task goal.")
    p_run.add_argument("--repo", required=True, help="Path to the target Java repo.")
    p_run.add_argument(
        "--config",
        default=None,
        help="Path to probe.yaml (optional; defaults are used otherwise).",
    )

    # map
    p_map = sub.add_parser("map", help="Render a CodeMap DOT graph for a repo.")
    p_map.add_argument("--repo", required=True, help="Path to the target Java repo.")
    p_map.add_argument(
        "--kind",
        choices=["package", "class"],
        default="package",
        help="Diagram kind (default: package).",
    )
    p_map.add_argument(
        "--package",
        default=None,
        help="Package to filter to (only with --kind class).",
    )

    # creds
    p_creds = sub.add_parser("creds", help="Manage credentials.")
    creds_sub = p_creds.add_subparsers(dest="creds_command", required=True)
    p_creds_status = creds_sub.add_parser("status", help="Show masked status of a key.")
    p_creds_status.add_argument("key", help="Credential key to inspect.")
    p_creds_update = creds_sub.add_parser("update", help="Update a credential value.")
    p_creds_update.add_argument("key", help="Credential key to update.")
    p_creds_clear = creds_sub.add_parser("clear", help="Clear a credential.")
    p_creds_clear.add_argument("key", help="Credential key to clear.")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point. Returns an exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    store = _get_store()

    if args.command == "init":
        init_creds(store)
        return 0
    if args.command == "run":
        run_task(args.goal, args.repo, config_path=args.config)
        return 0
    if args.command == "map":
        out = run_map(Path(args.repo), kind=args.kind, package=args.package)
        print(out)
        return 0
    if args.command == "creds":
        if args.creds_command == "status":
            creds_status(store, args.key)
            return 0
        if args.creds_command == "update":
            creds_update(store, args.key)
            return 0
        if args.creds_command == "clear":
            creds_clear(store, args.key)
            return 0
    # argparse enforces the subcommand, so this is unreachable.
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
