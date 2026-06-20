from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from videocenter.models.download import DownloadStatus, DownloadTask
from videocenter.models.history import WatchHistory
from videocenter.models.media import (
    Episode,
    LocalResource,
    Media,
    MediaStatus,
    MediaType,
    Season,
    Tag,
)


class ModelFactory:
    def __init__(self, session: Session) -> None:
        self.session = session

    def media(self, **overrides) -> Media:
        values = {
            "title": f"Test media {uuid4().hex[:8]}",
            "alternative_titles": [],
            "media_type": MediaType.MOVIE,
            "status": MediaStatus.PENDING,
            "directors": [],
            "actors": [],
            "regions": [],
            "languages": [],
            "genres": [],
        }
        values.update(overrides)
        return self._save(Media(**values))

    def local_resource(
        self,
        *,
        media: Media | None = None,
        **overrides,
    ) -> LocalResource:
        unique_name = f"video-{uuid4().hex}.mp4"
        values = {
            "media_id": media.id if media else None,
            "file_path": str((Path("data/testing-media") / unique_name).resolve()),
            "file_name": unique_name,
            "file_size": 1024,
            "mime_type": "video/mp4",
        }
        values.update(overrides)
        return self._save(LocalResource(**values))

    def tag(self, **overrides) -> Tag:
        name = overrides.pop("name", f"Tag {uuid4().hex[:8]}")
        values = {
            "name": name,
            "normalized_name": name.casefold(),
        }
        values.update(overrides)
        return self._save(Tag(**values))

    def season(
        self,
        *,
        media: Media,
        **overrides,
    ) -> Season:
        values = {
            "media_id": media.id,
            "season_number": 1,
            "title": "Season 1",
        }
        values.update(overrides)
        return self._save(Season(**values))

    def episode(
        self,
        *,
        season: Season,
        **overrides,
    ) -> Episode:
        values = {
            "season_id": season.id,
            "episode_number": 1,
            "title": "Episode 1",
        }
        values.update(overrides)
        return self._save(Episode(**values))

    def download_task(
        self,
        *,
        media: Media | None = None,
        **overrides,
    ) -> DownloadTask:
        values = {
            "media_id": media.id if media else None,
            "source_url": "https://example.com/test-video.mp4",
            "target_name": f"test-video-{uuid4().hex}.mp4",
            "status": DownloadStatus.WAITING,
            "progress": 0,
        }
        values.update(overrides)
        return self._save(DownloadTask(**values))

    def watch_history(
        self,
        *,
        media: Media,
        resource: LocalResource | None = None,
        **overrides,
    ) -> WatchHistory:
        values = {
            "media_id": media.id,
            "resource_id": resource.id if resource else None,
            "position_seconds": 30,
            "duration_seconds": 120,
        }
        values.update(overrides)
        return self._save(WatchHistory(**values))

    def _save(self, model):
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model
