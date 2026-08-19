"""Allow ``python -m biscuit`` as a shortcut for ``python -m biscuit.cli``."""

from biscuit.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
