import pytest
from unittest.mock import AsyncMock, patch

from app import trending_diff


def test_diff_finds_new_entries():
    today = {"items": [{"full_name": "a/x"}, {"full_name": "b/y"}]}
    yesterday = {"items": [{"full_name": "a/x"}]}
    new = trending_diff.find_new_entries(today, yesterday)
    assert len(new) == 1
    assert new[0]["full_name"] == "b/y"


def test_diff_empty_today():
    today = {"items": []}
    yesterday = {"items": [{"full_name": "a/x"}]}
    new = trending_diff.find_new_entries(today, yesterday)
    assert new == []


def test_diff_empty_yesterday():
    today = {"items": [{"full_name": "a/x"}]}
    yesterday = None
    new = trending_diff.find_new_entries(today, yesterday)
    assert new == []


def test_diff_no_new_when_all_overlap():
    today = {"items": [{"full_name": "a/x"}, {"full_name": "b/y"}]}
    yesterday = {"items": [{"full_name": "a/x"}, {"full_name": "b/y"}]}
    new = trending_diff.find_new_entries(today, yesterday)
    assert new == []


@pytest.mark.asyncio
async def test_detect_and_record_writes_events():
    """detect_and_record: when new entries exist, writes trending_new events."""
    today_data = {"items": [{"full_name": "a/x", "description": "d1", "url": "u1"}, {"full_name": "b/y", "description": "d2", "url": "u2"}]}
    yesterday_data = {"items": [{"full_name": "a/x"}]}

    with patch("app.trending_diff.get_daily_trending", new=AsyncMock(side_effect=[today_data, yesterday_data])), \
         patch("app.trending_diff.upload_monitor_events", new=AsyncMock()) as mock_upload:
        count = await trending_diff.detect_and_record("2026-06-01", "2026-05-31")

    assert count == 1
    mock_upload.assert_called_once()
    call_kwargs = mock_upload.call_args.kwargs
    assert call_kwargs["repo"] == "github-trending-trending-diff"
    assert len(call_kwargs["events"]) == 1
    assert call_kwargs["events"][0]["type"] == "trending_new"
    assert "b/y" in call_kwargs["events"][0]["title"]


@pytest.mark.asyncio
async def test_detect_and_record_returns_zero_on_no_new():
    """detect_and_record: when no new entries, returns 0 and does not call upload."""
    same_data = {"items": [{"full_name": "a/x"}]}

    with patch("app.trending_diff.get_daily_trending", new=AsyncMock(side_effect=[same_data, same_data])), \
         patch("app.trending_diff.upload_monitor_events", new=AsyncMock()) as mock_upload:
        count = await trending_diff.detect_and_record("2026-06-01", "2026-05-31")

    assert count == 0
    mock_upload.assert_not_called()


@pytest.mark.asyncio
async def test_detect_and_record_swallows_errors():
    """detect_and_record: returns 0 and logs warning on exception."""
    with patch("app.trending_diff.get_daily_trending", new=AsyncMock(side_effect=RuntimeError("DB down"))):
        count = await trending_diff.detect_and_record("2026-06-01", "2026-05-31")
    assert count == 0
