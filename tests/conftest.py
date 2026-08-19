from __future__ import annotations

from pathlib import Path

import pytest

from biscuit.config import AppConfig, ImageConfig, NarrationConfig, VideoConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def mini_story_path() -> Path:
    return FIXTURES / "mini_rescue.yaml"


@pytest.fixture
def example_story_path(repo_root: Path) -> Path:
    return repo_root / "stories" / "biscuit_in_the_snow.yaml"


@pytest.fixture
def test_config(tmp_path: Path, repo_root: Path) -> AppConfig:
    config = AppConfig(
        output_dir=tmp_path / "output",
        log_dir=tmp_path / "logs",
        characters_dir=repo_root / "characters",
        image=ImageConfig(provider="development", width=640, height=360),
        narration=NarrationConfig(provider="development", words_per_minute=180),
        video=VideoConfig(
            width=640,
            height=360,
            fps=15,
            encoder_preset="ultrafast",
            fade_seconds=0.12,
        ),
    )
    config.youtube.enabled = False
    return config
