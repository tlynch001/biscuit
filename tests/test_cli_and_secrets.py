from __future__ import annotations

from pathlib import Path

import pytest

from biscuit.cli import build_arg_parser, main


def test_cli_regenerate_image_parses() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(
        ["--story", "stories/x.yaml", "--regenerate-image", "4", "--regenerate-image", "7"]
    )
    assert args.regenerate_images == [4, 7]


def test_cli_regenerate_image_rejects_zero() -> None:
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--story", "stories/x.yaml", "--regenerate-image", "0"])


def test_gitignore_and_env_example_keep_secrets_out(repo_root: Path) -> None:
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore
    assert "config/config.yaml" in gitignore
    assert "secrets/*" in gitignore
    assert "output/" in gitignore

    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    assert "ELEVENLABS_API_KEY=" in env_example
    assert "ELEVENLABS_API_KEY=sk-" not in env_example
    for line in env_example.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            assert value.strip() == "", f"{key} should be empty in .env.example"

    example_config = (repo_root / "config" / "config.example.yaml").read_text(encoding="utf-8")
    assert "api_key:" not in example_config
    assert "ELEVENLABS_API_KEY" in example_config
    assert "OPENAI_API_KEY" in example_config
    assert "api_key_env: OPENAI_API_KEY" in example_config
    assert "provider: development" in example_config
    assert "youtube:" in example_config
    assert "enabled: false" in example_config
    assert "eleven_multilingual_v2" in example_config


def test_repo_does_not_contain_dotenv(repo_root: Path) -> None:
    assert not (repo_root / ".env").exists()


def test_cli_dry_run_succeeds(example_story_path: Path, repo_root: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    config = tmp_path / "config.yaml"
    config.write_text(
        "\n".join(
            [
                f"output_dir: {tmp_path / 'out'}",
                f"log_dir: {tmp_path / 'logs'}",
                f"characters_dir: {repo_root / 'characters'}",
                "youtube:",
                "  enabled: false",
            ]
        ),
        encoding="utf-8",
    )
    code = main(["--config", str(config), "--story", str(example_story_path), "--dry-run"])
    assert code == 0


def test_cli_missing_story_returns_error(repo_root: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    config = tmp_path / "config.yaml"
    config.write_text("youtube:\n  enabled: false\n", encoding="utf-8")
    code = main(["--config", str(config), "--story", str(tmp_path / "missing.yaml")])
    assert code == 1
