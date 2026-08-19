"""Command-line entry point.

Usage::

    python -m biscuit.cli --story stories/biscuit_in_the_snow.yaml
    python -m biscuit.cli --config config/config.yaml --story stories/biscuit_in_the_snow.yaml
    python -m biscuit.cli --story stories/biscuit_in_the_snow.yaml --from-stage assemble --force
    python -m biscuit.cli --story stories/biscuit_in_the_snow.yaml --regenerate-image 4
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from biscuit.config import load_config
from biscuit.exceptions import BiscuitError, ConfigurationError
from biscuit.logging_setup import configure_logging
from biscuit.pipeline import StoryPipeline
from biscuit.stages import STAGES

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_CANDIDATES = (
    Path("config/config.yaml"),
    Path("config/config.example.yaml"),
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="biscuit",
        description="Generate a narrated story video from a YAML story file.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to YAML configuration (default: config/config.yaml, then config.example.yaml).",
    )
    parser.add_argument(
        "--story",
        required=True,
        help="Path to the story YAML file.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug-level logging.")
    parser.add_argument(
        "--from-stage",
        default="parse",
        choices=STAGES,
        help="First stage to execute (earlier artifacts are reused).",
    )
    parser.add_argument(
        "--through-stage",
        default="publish",
        choices=STAGES,
        help="Last stage to execute.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate artifacts even when a matching cache exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the story and print the plan without generating assets.",
    )
    parser.add_argument(
        "--new-run",
        action="store_true",
        help="Write into a timestamped output subdirectory instead of reusing output/<story_id>/.",
    )
    parser.add_argument(
        "--regenerate-image",
        action="append",
        type=_positive_scene_index,
        dest="regenerate_images",
        metavar="N",
        default=None,
        help=(
            "1-based scene index to regenerate even when a cached PNG exists. "
            "Repeatable. Paid image providers otherwise reuse stale stills to avoid extra API spend."
        ),
    )
    return parser


def _positive_scene_index(value: str) -> int:
    try:
        index = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"scene index must be an integer, got {value!r}") from exc
    if index < 1:
        raise argparse.ArgumentTypeError("scene indexes are 1-based (the number in 001.png, 002.png, …).")
    return index


def _resolve_config_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    for candidate in _DEFAULT_CONFIG_CANDIDATES:
        if candidate.exists():
            return candidate
    raise ConfigurationError(
        "No configuration file found. Copy config/config.example.yaml to "
        "config/config.yaml or pass --config."
    )


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        config_path = _resolve_config_path(args.config)
        config = load_config(config_path)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    story_id = Path(args.story).stem
    log_path = configure_logging(config.log_dir, story_id, verbose=args.verbose)
    logger.info("Logging to %s", log_path)
    logger.info("Using config %s", config_path)

    try:
        pipeline = StoryPipeline(config)
        manifest = pipeline.run(
            args.story,
            from_stage=args.from_stage,
            through_stage=args.through_stage,
            force=args.force,
            dry_run=args.dry_run,
            new_run=args.new_run,
            regenerate_images=args.regenerate_images or [],
        )
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        return 2
    except BiscuitError as exc:
        logger.exception("Fatal error: %s", exc)
        return 1
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected fatal error.")
        return 1

    logger.info("Finished story %s (%d scenes)", manifest.story_id, len(manifest.scenes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
