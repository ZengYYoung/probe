"""Enable ``python -m probe`` to invoke the CLI entry point."""

from probe.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
