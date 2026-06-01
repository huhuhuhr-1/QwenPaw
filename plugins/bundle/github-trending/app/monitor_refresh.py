"""订阅 repo 详情刷新与 diff。"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from app.database import (
    get_subscriptions,
    get_watch_log,
    list_watch_logs_by_subscription,
    upsert_watch_log,
    upload_monitor_events,
)

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

CONCURRENCY = 5
REQUEST_TIMEOUT_SEC = 20
STARS_CHANGE_THRESHOLD = 5


def parse_repo_html(html: str, full_name: str) -> Dict[str, Any]:
    """解析 GitHub repo HTML 提取 stars / forks / language / description / last_commit。"""
    soup = BeautifulSoup(html, "lxml")
    info: Dict[str, Any] = {
        "stars": 0,
        "forks": 0,
        "language": "",
        "description": "",
        "last_commit": None,
    }

    desc_p = soup.select_one("p.f4.my-3, p[data-test-selector='repo-description']")
    if not desc_p:
        for p in soup.select("article p, .BorderGrid p, body > p"):
            text = p.get_text(strip=True)
            if 5 < len(text) < 500 and "github.com" not in text.lower():
                desc_p = p
                break
    if desc_p:
        info["description"] = desc_p.get_text(strip=True)

    lang_span = soup.select_one("span[itemprop='programmingLanguage']")
    if lang_span:
        info["language"] = lang_span.get_text(strip=True)

    for a in soup.select("a"):
        href = a.get("href", "") or ""
        text = a.get_text(strip=True).replace(",", "")
        if "/stargazers" in href and text.isdigit():
            info["stars"] = int(text)
            break

    for a in soup.select("a"):
        href = a.get("href", "") or ""
        text = a.get_text(strip=True).replace(",", "")
        if "/network/members" in href and text.isdigit():
            info["forks"] = int(text)
            break

    rel_time = soup.select_one("relative-time[datetime]")
    if rel_time:
        info["last_commit"] = rel_time.get("datetime")

    return info


def diff_watch_log(
    old: Optional[Dict[str, Any]],
    new: Dict[str, Any],
    threshold: int = STARS_CHANGE_THRESHOLD,
) -> List[Dict[str, str]]:
    """对比新旧 watch_log,返回要写的事件列表。"""
    events: List[Dict[str, str]] = []
    if old is None:
        return events
    star_delta = new["stars"] - old.get("stars", 0)
    if abs(star_delta) >= threshold:
        events.append({
            "type": "star_update",
            "title": f"Stars {old.get('stars', 0)} → {new['stars']}",
            "body": f"stars: {old.get('stars', 0)} → {new['stars']} (delta {star_delta:+d})",
        })
    if new.get("language") and new["language"] != old.get("language"):
        events.append({
            "type": "repo_meta_update",
            "title": f"Language changed",
            "body": f"{old.get('language') or '?'} → {new['language']}",
        })
    if new.get("description") and new["description"] != old.get("description"):
        events.append({
            "type": "repo_meta_update",
            "title": f"Description changed",
            "body": new["description"][:200],
        })
    return events


async def _fetch_repo_html(full_name: str) -> str:
    url = f"https://github.com/{full_name}"
    headers = {"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SEC, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


async def refresh_one_repo(full_name: str, subscription_id: int) -> Dict[str, Any]:
    """拉一个 repo 详情,写 watch_log,变化超过阈值发事件。"""
    try:
        html = await _fetch_repo_html(full_name)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        logger.warning("Failed to fetch %s: %s", full_name, err)
        await upload_monitor_events(
            repo=full_name,
            repo_info={"stars": 0, "forks": 0, "language": "", "description": ""},
            events=[{
                "type": "refresh_error",
                "title": f"Failed to refresh {full_name}",
                "body": err,
                "url": "",
                "version": "",
                "time": "",
            }],
        )
        return {"repo": full_name, "ok": False, "error": err}

    info = parse_repo_html(html, full_name)
    old_log = await get_watch_log(subscription_id, full_name)
    events = diff_watch_log(old_log, info)

    if events:
        repo_info = {
            "stars": info["stars"],
            "forks": info["forks"],
            "language": info["language"],
            "description": info["description"],
        }
        await upload_monitor_events(
            repo=full_name,
            repo_info=repo_info,
            events=[
                {**e, "url": f"https://github.com/{full_name}", "version": "", "time": ""}
                for e in events
            ],
        )

    await upsert_watch_log(subscription_id, full_name, info)
    return {"repo": full_name, "ok": True, "events": len(events), "stars": info["stars"]}


async def refresh_all_subscribed_repos() -> Dict[str, Any]:
    """并发拉所有订阅 repo,返回汇总。"""
    subs = await get_subscriptions()
    if not subs:
        return {"refreshed": 0, "errors": 0}

    sem = asyncio.Semaphore(CONCURRENCY)

    async def _run(sub: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            target = sub["target"]
            return await refresh_one_repo(target, sub["id"])

    results = await asyncio.gather(
        *[_run(s) for s in subs], return_exceptions=True
    )
    ok = sum(1 for r in results if isinstance(r, dict) and r.get("ok"))
    err = sum(1 for r in results if not (isinstance(r, dict) and r.get("ok")))
    logger.info("Repo refresh: %d ok, %d err", ok, err)
    return {"refreshed": ok, "errors": err}
