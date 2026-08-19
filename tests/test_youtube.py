from __future__ import annotations

from pathlib import Path

from biscuit.config import YouTubeConfig
from biscuit.youtube import publish_video


def test_youtube_disabled_never_calls_client(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")

    def boom(_config):
        raise AssertionError("client_factory must not be called when disabled")

    result = publish_video(
        video_path=video,
        title="T",
        description="D",
        thumbnail_path=None,
        config=YouTubeConfig(enabled=False),
        client_factory=boom,
    )
    assert result.status == "disabled"
    assert result.ok


def test_youtube_enabled_uploads_and_sets_thumbnail(tmp_path: Path, monkeypatch) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake-mp4")
    thumb = tmp_path / "thumbnail.png"
    thumb.write_bytes(b"fake-png")
    client = object()
    captured: dict = {}

    def factory(config: YouTubeConfig):
        captured["config"] = config
        return client

    def fake_upload(cli, path, **kwargs):
        captured["upload_client"] = cli
        captured["video"] = path
        captured["title"] = kwargs["title"]
        return "abc123"

    def fake_thumb(cli, video_id, path):
        captured["thumb_id"] = video_id
        captured["thumb_path"] = path

    monkeypatch.setattr("biscuit.youtube._upload_video", fake_upload)
    monkeypatch.setattr("biscuit.youtube._set_thumbnail", fake_thumb)

    result = publish_video(
        video_path=video,
        title="Biscuit in the Snow",
        description="A story",
        thumbnail_path=thumb,
        config=YouTubeConfig(enabled=True, privacy="unlisted"),
        client_factory=factory,
    )
    assert result.status == "success"
    assert result.video_id == "abc123"
    assert result.video_url.endswith("abc123")
    assert result.thumbnail_uploaded is True
    assert captured["title"] == "Biscuit in the Snow"
    assert captured["upload_client"] is client


def test_youtube_skips_duplicate_without_force(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")

    def boom(_config):
        raise AssertionError("should not upload duplicates")

    result = publish_video(
        video_path=video,
        title="T",
        description="D",
        thumbnail_path=None,
        config=YouTubeConfig(enabled=True),
        already_uploaded_id="oldid",
        client_factory=boom,
    )
    assert result.status == "skipped_duplicate"
    assert result.video_id == "oldid"


def test_pipeline_publish_stage_does_not_upload_when_disabled(
    mini_story_path, test_config, monkeypatch
) -> None:
    from biscuit.artifacts import ArtifactStore
    from biscuit.pipeline import StoryPipeline
    from biscuit import youtube

    original = youtube.publish_video

    def wrapped(**kwargs):
        assert kwargs["config"].enabled is False
        return original(**kwargs)

    monkeypatch.setattr("biscuit.pipeline.publish_video", wrapped)
    pipeline = StoryPipeline(test_config)
    store = ArtifactStore(test_config.output_dir, "mini_rescue")
    pipeline.run(mini_story_path, store=store, through_stage="expand")
    pipeline.run(mini_story_path, store=store, from_stage="publish", through_stage="publish")
