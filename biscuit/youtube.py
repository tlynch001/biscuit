"""Optional YouTube Data API v3 publishing.

Disabled by default (``youtube.enabled: false``). Importing this package
has no side effects: Google libraries are imported only inside functions
that run after the enabled check. Tests never upload.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from biscuit.config import YouTubeConfig
from biscuit.exceptions import BiscuitError

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeAuthError(BiscuitError):
    """Raised when OAuth credentials could not be loaded."""


class YouTubeUploadError(BiscuitError):
    """Raised internally when an upload API call fails."""


@dataclass
class YouTubePublishResult:
    status: str
    video_id: str | None = None
    video_url: str | None = None
    video_error: str | None = None
    thumbnail_uploaded: bool = False
    thumbnail_error: str | None = None
    message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"disabled", "skipped_duplicate", "success"}


def _install_hint() -> str:
    return (
        "YouTube publishing requires the optional google-api-python-client / "
        "google-auth-oauthlib packages. Install with: pip install 'biscuit[youtube]'"
    )


def get_credentials(config: YouTubeConfig) -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:  # pragma: no cover
        raise YouTubeAuthError(_install_hint()) from exc

    token_path = Path(config.token_path)
    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except (ValueError, OSError) as exc:
            raise YouTubeAuthError(f"Could not read YouTube token file {token_path}: {exc}") from exc

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(token_path, creds)

    if creds and creds.valid:
        return creds

    return _interactive_credentials(config, token_path)


def _save_token(token_path: Path, creds: Any) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")


def _interactive_credentials(config: YouTubeConfig, token_path: Path) -> Any:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:  # pragma: no cover
        raise YouTubeAuthError(_install_hint()) from exc

    secret_path = Path(config.client_secret_path)
    if not secret_path.exists():
        raise YouTubeAuthError(
            f"YouTube client secret not found at {secret_path}. Download a Desktop "
            "OAuth client JSON from Google Cloud Console and place it there. "
            "Never commit that file."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(token_path, creds)
    return creds


def build_client(config: YouTubeConfig) -> Any:
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover
        raise YouTubeUploadError(_install_hint()) from exc
    return build("youtube", "v3", credentials=get_credentials(config), cache_discovery=False)


def _upload_video(
    client: Any,
    video_path: Path,
    *,
    title: str,
    description: str,
    category_id: str,
    privacy_status: str,
) -> str:
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {"title": title, "description": description, "categoryId": category_id},
        "status": {"privacyStatus": privacy_status},
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=-1, resumable=True)
    request = client.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _status, response = request.next_chunk()
    return str(response["id"])


def _set_thumbnail(client: Any, video_id: str, thumbnail_path: Path) -> None:
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(thumbnail_path), mimetype="image/png")
    client.thumbnails().set(videoId=video_id, media_body=media).execute()


def publish_video(
    *,
    video_path: Path,
    title: str,
    description: str,
    thumbnail_path: Path | None,
    config: YouTubeConfig,
    force: bool = False,
    already_uploaded_id: str | None = None,
    client_factory: Callable[[YouTubeConfig], Any] = build_client,
) -> YouTubePublishResult:
    """Upload a finished video package. Never called by tests with enabled=True
    against a real client — inject ``client_factory`` in unit tests.

    If ``config.enabled`` is false, returns immediately with no I/O.
    """

    if not config.enabled:
        logger.debug("YouTube publishing is disabled (youtube.enabled: false); skipping.")
        return YouTubePublishResult(status="disabled", message="youtube.enabled is false")

    if already_uploaded_id and not force:
        message = f"YouTube upload skipped: already uploaded as {already_uploaded_id}"
        logger.info(message)
        return YouTubePublishResult(
            status="skipped_duplicate",
            video_id=already_uploaded_id,
            video_url=f"https://www.youtube.com/watch?v={already_uploaded_id}",
            message=message,
        )

    if not video_path.exists():
        message = f"No video found at {video_path}; cannot publish to YouTube."
        logger.error(message)
        return YouTubePublishResult(status="failed", video_error=message)

    logger.info("Uploading video to YouTube...")
    try:
        client = client_factory(config)
        video_id = _upload_video(
            client,
            video_path,
            title=title,
            description=description,
            category_id=config.category_id,
            privacy_status=config.privacy,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("YouTube video upload failed: %s", exc)
        return YouTubePublishResult(status="failed", video_error=str(exc))

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    result = YouTubePublishResult(status="success", video_id=video_id, video_url=video_url)

    if thumbnail_path and thumbnail_path.exists():
        try:
            _set_thumbnail(client, video_id, thumbnail_path)
            result.thumbnail_uploaded = True
        except Exception as exc:  # noqa: BLE001
            result.thumbnail_error = str(exc)
            logger.error("Thumbnail upload failed (video %s is fine): %s", video_id, exc)
    return result
