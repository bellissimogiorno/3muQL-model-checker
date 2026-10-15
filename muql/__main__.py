"""Enable ``python -m muql`` without installing a console entry point."""

from .cli import main

raise SystemExit(main())
