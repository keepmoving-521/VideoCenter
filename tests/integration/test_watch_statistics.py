from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from videocenter.models.history import WatchDailyStat

pytestmark = pytest.mark.integration


def test_progress_reports_accumulate_explicit_watched_seconds(
    api_client: TestClient,
    model_factory,
):
    media = model_factory.media()
    resource = model_factory.local_resource(media=media, duration_seconds=100)

    api_client.put(
        f"/api/v1/stream/{resource.id}/progress",
        json={"position_seconds": 60, "watched_seconds": 20},
    )
    api_client.put(
        f"/api/v1/stream/{resource.id}/progress",
        json={"position_seconds": 95, "watched_seconds": 15},
    )

    summary = api_client.get("/api/v1/history/stats/summary").json()

    assert summary == {
        "total_watched_seconds": 35,
        "total_watched_minutes": 0.58,
        "total_watched_hours": 0.01,
        "watched_media_count": 1,
        "active_days": 1,
        "average_daily_seconds": 35,
        "completed_count": 1,
    }


def test_progress_reports_infer_positive_position_delta_when_omitted(
    api_client: TestClient,
    model_factory,
):
    media = model_factory.media()
    resource = model_factory.local_resource(media=media, duration_seconds=200)

    for position in (30, 50, 10):
        api_client.put(
            f"/api/v1/stream/{resource.id}/progress",
            json={"position_seconds": position},
        )

    summary = api_client.get("/api/v1/history/stats/summary").json()

    assert summary["total_watched_seconds"] == 50


def test_daily_watch_statistics_fill_dates_without_activity(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    media = model_factory.media()
    today = date.today()
    db_session.add_all(
        [
            WatchDailyStat(
                stat_date=today - timedelta(days=2),
                media_id=media.id,
                watched_seconds=120,
                completion_count=0,
            ),
            WatchDailyStat(
                stat_date=today,
                media_id=media.id,
                watched_seconds=60,
                completion_count=1,
            ),
        ]
    )
    db_session.commit()

    payload = api_client.get(
        "/api/v1/history/stats/daily",
        params={
            "start_date": (today - timedelta(days=2)).isoformat(),
            "end_date": today.isoformat(),
        },
    ).json()

    assert [item["watched_seconds"] for item in payload["items"]] == [120, 0, 60]
    assert [item["watched_minutes"] for item in payload["items"]] == [2, 0, 1]
    assert payload["items"][-1]["completed_count"] == 1


@pytest.mark.parametrize(
    ("params", "code"),
    [
        (
            {"start_date": "2026-06-22", "end_date": "2026-06-21"},
            "INVALID_WATCH_STATS_DATE_RANGE",
        ),
        (
            {"start_date": "2025-01-01", "end_date": "2026-06-22"},
            "WATCH_STATS_RANGE_TOO_LARGE",
        ),
    ],
)
def test_daily_watch_statistics_validate_date_range(
    api_client: TestClient,
    api_assertions,
    params: dict[str, str],
    code: str,
):
    api_assertions.assert_error(
        api_client.get("/api/v1/history/stats/daily", params=params),
        status_code=400,
        code=code,
    )


def test_clearing_history_also_clears_watch_statistics(
    api_client: TestClient,
    model_factory,
):
    media = model_factory.media()
    resource = model_factory.local_resource(media=media)
    api_client.put(
        f"/api/v1/stream/{resource.id}/progress",
        json={"position_seconds": 30, "watched_seconds": 30},
    )

    api_client.delete("/api/v1/history/clear")

    summary = api_client.get("/api/v1/history/stats/summary").json()
    assert summary["total_watched_seconds"] == 0
    assert summary["watched_media_count"] == 0
