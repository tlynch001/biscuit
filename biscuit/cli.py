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
from biscuit.exceptions import ArtDirectionError, BiscuitError, ConfigurationError
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
    parser.add_argument(
        "--register-reference",
        default=None,
        metavar="ID",
        help="Register a local image as logical reference asset ID (requires --reference-file).",
    )
    parser.add_argument(
        "--reference-file",
        default=None,
        help="Local image path used with --register-reference.",
    )
    parser.add_argument(
        "--reference-category",
        default=None,
        choices=("character", "location", "vehicle", "prop", "environmental", "composition"),
        help="Optional category when registering a reference.",
    )
    parser.add_argument(
        "--approve-reference",
        action="append",
        dest="approve_references",
        metavar="ID",
        default=None,
        help="Mark a reference asset approved. Repeatable.",
    )
    parser.add_argument(
        "--reject-reference",
        action="append",
        dest="reject_references",
        metavar="ID",
        default=None,
        help="Mark a reference asset rejected. Repeatable.",
    )
    parser.add_argument(
        "--generate-reference",
        action="append",
        dest="generate_references",
        metavar="ID",
        default=None,
        help="Generate a candidate image for a planned reference. Does not approve it.",
    )
    parser.add_argument(
        "--promote-shot",
        type=_positive_scene_index,
        default=None,
        metavar="N",
        help="Promote generated scene N to a composition reference (requires --as-reference).",
    )
    parser.add_argument(
        "--as-reference",
        default=None,
        metavar="ID",
        help="Logical asset id used with --promote-shot.",
    )
    parser.add_argument(
        "--force-references",
        action="store_true",
        help="Allow replacing approved reference images. Ordinary --force will not do this.",
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
            register_reference=args.register_reference,
            reference_file=args.reference_file,
            reference_category=args.reference_category,
            approve_references=args.approve_references or [],
            reject_references=args.reject_references or [],
            generate_references=args.generate_references or [],
            promote_shot=args.promote_shot,
            as_reference=args.as_reference,
            force_references=args.force_references,
        )
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        return 2
    except ArtDirectionError as exc:
        logger.error("Art direction: %s", exc)
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
