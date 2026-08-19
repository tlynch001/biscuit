"""Pipeline stage names.

The orchestrator uses this ordered list for ``--from-stage`` / ``--through-stage``.
Each stage is independently inspectable via artifacts on disk.
"""

from __future__ import annotations

STAGES: tuple[str, ...] = (
    "parse",
    "expand",
    "prompts",
    "narrate",
    "illustrate",
    "assemble",
    "package",
    "publish",
)


def stage_index(name: str) -> int:
    try:
        return STAGES.index(name)
    except ValueError as exc:
        raise ValueError(f"Unknown stage {name!r}. Available: {', '.join(STAGES)}") from exc
