"""GitHub Trending 自动采集器

参考实现: /opt/github/github-data-fetch/app/modules/collection/trending_discovery.py
(本文件是简化版,只做抓取 → upload_trending,不写新表)

设计要点:
- 每 `collect_interval_min` 分钟跑一轮,每轮按 `collect_languages` 列表
  逐个爬 github.com/trending/{lang}?since={collect_period}
- 失败: logger.error + 写一条 monitor_events(type=collector_error),
  写到 `github-trending-collector` 这个伪仓库下,订阅页可看到
- 防反爬:语言之间 sleep 3s,GitHub 不会触发限流
- 写库复用现有 `upload_trending()` (按 date+language merge),不写新表
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import upload_monitor_events, upload_trending

logger = logging.getLogger(__name__)

# 防 GitHub 反爬:两次抓取之间 sleep
LANGUAGE_INTERVAL_SEC = 3.0

# GitHub Trending 周期参数
_SINCE_MAP = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
}

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 伪仓库:用来在订阅监控页显示 collector 自身的错误
_COLLECTOR_REPO = "github-trending-collector"


# ── 抓取层 ──────────────────────────────────────────────────────────


async def _fetch_trending_html(period: str, language: Optional[str]) -> str:
    """抓 github.com/trending 的 HTML 原文,出错时抛异常。"""
    since = _SINCE_MAP.get(period, "daily")
    url = f"https://github.com/trending/{language or ''}?since={since}"
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    # github_token 留作未来切到 GitHub Search API 时用;HTML 抓取不需要
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


def _parse_trending_html(html: str) -> list[dict]:
    """解析 GitHub Trending HTML,返回结构化 repo 列表。"""
    soup = BeautifulSoup(html, "lxml")
    repos: list[dict] = []

    for article in soup.select("article.Box-row"):
        link = article.select_one("h2 a")
        if not link:
            continue
        href = link.get("href", "")
        if not href.startswith("/"):
            continue
        parts = href.lstrip("/").split("/")
        if len(parts) < 2:
            continue
        owner, name = parts[0], parts[1]
        full_name = f"{owner}/{name}"

        desc_elem = article.select_one("p")
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        language = ""
        prog_lang = article.select_one("span[itemprop='programmingLanguage']")
        if prog_lang:
            language = prog_lang.get_text(strip=True)

        stars = 0
        for a_tag in article.select("a"):
            a_href = a_tag.get("href", "") or ""
            if "/stargazers" in a_href:
                text = a_tag.get_text(strip=True)
                try:
                    stars = int(text.replace(",", ""))
                    break
                except ValueError:
                    pass

        stars_delta = 0
        for span in article.select("span"):
            text = span.get_text(strip=True)
            if "stars today" in text:
                try:
                    stars_delta = int(text.split()[0].replace(",", ""))
                except ValueError:
                    pass
                break

        forks = 0
        for a_tag in article.select("a"):
            a_href = a_tag.get("href", "") or ""
            if "/network/members" in a_href:
                text = a_tag.get_text(strip=True)
                try:
                    forks = int(text.replace(",", ""))
                    break
                except ValueError:
                    pass

        repos.append(
            {
                "rank": 0,  # rank 在 collect_once 里按 enumerate 重写
                "owner": owner,
                "name": name,
                "full_name": full_name,
                "description": description,
                "language": language,
                "stars": stars,
                "stars_delta": stars_delta,
                "forks": forks,
                "url": f"https://github.com/{full_name}",
            }
        )

    return repos


def _to_trending_items(repos: list[dict]) -> list[dict]:
    """把 _parse_trending_html 的结果转成 upload_trending 期望的 items。"""
    items: list[dict] = []
    for i, r in enumerate(repos, start=1):
        items.append(
            {
                "rank": i,
                "name": r["name"],
                "owner": r["owner"],
                "full_name": r["full_name"],
                "description": r.get("description") or None,
                "language": r.get("language") or None,
                "stars": r.get("stars", 0),
                "stars_delta": r.get("stars_delta", 0),
                "forks": r.get("forks", 0),
                "url": r["url"],
            }
        )
    return items


# ── 失败记录 ────────────────────────────────────────────────────────


async def _record_error(language: str, period: str, error: str) -> None:
    """把采集失败写到 monitor_events,订阅页可见。"""
    try:
        await upload_monitor_events(
            repo=_COLLECTOR_REPO,
            repo_info={"stars": 0, "forks": 0, "open_issues": 0,
                       "language": "python", "description": "Trending collector"},
            events=[
                {
                    "type": "collector_error",
                    "title": f"Trending collection failed: {language or 'all'} ({period})",
                    "body": error,
                    "url": "",
                    "version": "",
                    "time": datetime.now().isoformat(),
                }
            ],
        )
    except Exception as e:  # noqa: BLE001
        # 错误回写失败不能拖垮采集循环
        logger.warning("Failed to record collector error: %s", e)


# ── 单次采集 + 后台循环 ─────────────────────────────────────────────


async def _collect_language(period: str, language: str, today: str) -> dict:
    """采集一个语言,返回 {"ok": bool, "count": int, "error": str}。"""
    try:
        html = await _fetch_trending_html(period, language or None)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        logger.error("Fetch failed: lang=%s period=%s err=%s", language or "all", period, err)
        await _record_error(language, period, err)
        return {"ok": False, "count": 0, "error": err}

    repos = _parse_trending_html(html)
    if not repos:
        err = "no repos parsed (GitHub may be blocking or HTML structure changed)"
        logger.warning("No repos: lang=%s period=%s", language or "all", period)
        await _record_error(language, period, err)
        return {"ok": False, "count": 0, "error": err}

    items = _to_trending_items(repos)
    await upload_trending(today, language or "all", items, summary=None)
    logger.info(
        "Collected: lang=%s period=%s count=%d", language or "all", period, len(items)
    )
    return {"ok": True, "count": len(items), "error": ""}


async def collect_once(period: Optional[str] = None) -> dict:
    """跑一轮:遍历 collect_languages 全部采一次。返回汇总。"""
    from app.settings import get_runtime_settings
    runtime = await get_runtime_settings()
    period = period or runtime["collect_period"]
    today = datetime.now().strftime("%Y-%m-%d")
    ok_langs: list[str] = []
    err_langs: list[dict] = []

    for lang in runtime["collect_languages"]:
        # 空串代表 "all"(github.com/trending 不带语言段)
        lang_norm = lang.strip() if isinstance(lang, str) else lang
        result = await _collect_language(period, lang_norm, today)
        if result["ok"]:
            ok_langs.append(lang_norm or "all")
        else:
            err_langs.append({"lang": lang_norm or "all", "error": result["error"]})
        # 语言间 sleep 保护 GitHub
        await asyncio.sleep(LANGUAGE_INTERVAL_SEC)

    summary = {
        "period": period,
        "date": today,
        "ok": ok_langs,
        "errors": err_langs,
    }
    logger.info("Round done: ok=%d, err=%d", len(ok_langs), len(err_langs))

    # 触发订阅 repo 刷新 + trending diff(不阻塞主流程)
    yesterday = (datetime.now().timestamp() - 86400)
    from datetime import datetime as dt
    yest_str = dt.fromtimestamp(yesterday).strftime("%Y-%m-%d")
    asyncio.create_task(_post_round_refresh(today, yest_str))

    return summary


async def run_collector_loop() -> None:
    """后台长跑任务:每 collect_interval_min 分钟跑一轮。失败不退出。"""
    from app.settings import get_runtime_settings
    while True:
        try:
            runtime = await get_runtime_settings()
            if not runtime["collect_enabled"]:
                logger.debug("Collector disabled, sleeping 60s")
                await asyncio.sleep(60)
                continue
            await collect_once()
        except Exception as e:  # noqa: BLE001
            logger.exception("Collector loop tick crashed: %s", e)
        # 重新读 interval(支持运行时变更)
        runtime = await get_runtime_settings()
        interval_sec = max(1, int(runtime["collect_interval_min"])) * 60
        await asyncio.sleep(interval_sec)


async def _post_round_refresh(today: str, yesterday: str) -> None:
    """一轮采集完后:刷新订阅 repo + 检测 trending 新进榜。失败不影响主流程。"""
    try:
        from app.monitor_refresh import refresh_all_subscribed_repos
        from app.trending_diff import detect_and_record
        await asyncio.gather(
            refresh_all_subscribed_repos(),
            detect_and_record(today, yesterday, language="all"),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Post-round refresh failed: %s", e)
