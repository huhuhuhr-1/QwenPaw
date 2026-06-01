import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app import monitor_refresh


def test_parse_repo_html_basic():
    html = """
    <html><body>
    <h1>owner / name</h1>
    <article>
        <span itemprop="programmingLanguage">Python</span>
        <p>Some description text</p>
        <a href="/owner/name/stargazers">1,234</a>
        <a href="/owner/name/network/members">56</a>
        <relative-time datetime="2026-05-30T10:00:00Z">3 days ago</relative-time>
    </article>
    </body></html>
    """
    info = monitor_refresh.parse_repo_html(html, "owner/name")
    assert info["stars"] == 1234
    assert info["forks"] == 56
    assert info["language"] == "Python"
    assert info["description"] == "Some description text"
    assert info["last_commit"] is not None


def test_parse_repo_html_handles_missing_fields():
    html = "<html><body><h1>owner / name</h1></body></html>"
    info = monitor_refresh.parse_repo_html(html, "owner/name")
    assert info["stars"] == 0
    assert info["forks"] == 0
    assert info["language"] == ""
    assert info["description"] == ""


def test_diff_returns_star_update_when_above_threshold():
    old = {"stars": 100, "forks": 10, "language": "Python", "description": "A"}
    new = {"stars": 110, "forks": 10, "language": "Python", "description": "A"}
    events = monitor_refresh.diff_watch_log(old, new, threshold=5)
    assert len(events) == 1
    assert events[0]["type"] == "star_update"
    assert "100 → 110" in events[0]["body"]


def test_diff_returns_no_event_when_below_threshold():
    old = {"stars": 100, "forks": 10, "language": "Python", "description": "A"}
    new = {"stars": 102, "forks": 10, "language": "Python", "description": "A"}
    events = monitor_refresh.diff_watch_log(old, new, threshold=5)
    assert events == []


def test_diff_returns_meta_update_on_description_change():
    old = {"stars": 100, "forks": 10, "language": "Python", "description": "A"}
    new = {"stars": 100, "forks": 10, "language": "Python", "description": "B"}
    events = monitor_refresh.diff_watch_log(old, new, threshold=5)
    assert any(e["type"] == "repo_meta_update" for e in events)


def test_parse_count_handles_abbreviated_formats():
    from app.monitor_refresh import _parse_count
    assert _parse_count("1,234") == 1234
    assert _parse_count("1.2k") == 1200
    assert _parse_count("3.4K") == 3400
    assert _parse_count("1.5m") == 1_500_000
    assert _parse_count("2.0b") == 2_000_000_000
    assert _parse_count("") == 0
    assert _parse_count("not a number") == 0
