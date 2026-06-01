"""GitHub Trend Hub 数据库"""

import aiosqlite
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.db_path


async def get_db():
    """获取数据库连接"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """初始化数据库"""
    db = await get_db()
    try:
        # 热榜数据（按天聚合）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_trending (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                language VARCHAR(50) DEFAULT 'all',
                total_count INTEGER DEFAULT 0,
                updated_count INTEGER DEFAULT 0,
                summary TEXT,
                data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 项目索引
        await db.execute("""
            CREATE TABLE IF NOT EXISTS repos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name VARCHAR(200) UNIQUE NOT NULL,
                owner VARCHAR(100),
                name VARCHAR(100),
                url VARCHAR(500),
                description TEXT,
                language VARCHAR(50),
                stars INTEGER DEFAULT 0,
                forks INTEGER DEFAULT 0,
                first_seen DATE,
                last_seen DATE,
                appearances INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 项目历史趋势
        await db.execute("""
            CREATE TABLE IF NOT EXISTS repo_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER,
                date DATE NOT NULL,
                rank INTEGER,
                stars INTEGER,
                stars_delta INTEGER,
                forks INTEGER,
                description TEXT,
                language VARCHAR(50),
                analysis TEXT,
                fetched_at DATETIME,
                UNIQUE(repo_id, date),
                FOREIGN KEY (repo_id) REFERENCES repos(id)
            )
        """)

        # 订阅列表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target VARCHAR(200) NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                notify_enabled BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 监控动态
        await db.execute("""
            CREATE TABLE IF NOT EXISTS monitor_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id INTEGER,
                repo_name VARCHAR(200),
                event_type VARCHAR(20) NOT NULL,
                title TEXT,
                body TEXT,
                url VARCHAR(500),
                version VARCHAR(50),
                event_time DATETIME,
                is_read BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
            )
        """)

        # 仓库缓存
        await db.execute("""
            CREATE TABLE IF NOT EXISTS watched_repos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name VARCHAR(200) UNIQUE NOT NULL,
                stars INTEGER DEFAULT 0,
                forks INTEGER DEFAULT 0,
                open_issues INTEGER DEFAULT 0,
                language VARCHAR(50),
                last_commit DATETIME,
                last_release DATETIME,
                description TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 分析报告
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                type VARCHAR(20) NOT NULL,
                source VARCHAR(20) DEFAULT 'llm',
                content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 索引
        await db.execute("CREATE INDEX IF NOT EXISTS idx_trending_date ON daily_trending(date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_repos_name ON repos(full_name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_history_repo ON repo_history(repo_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_history_date ON repo_history(date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_events_repo ON monitor_events(repo_name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON monitor_events(event_time)")

        await db.commit()
        logger.info("Database initialized")
    finally:
        await db.close()


# ── 热榜操作 ──


async def upload_trending(date_str: str, language: str, items: List[Dict], summary: str = None):
    """上传热榜数据（按天 merge）"""
    db = await get_db()
    try:
        # 获取现有数据
        row = await db.execute(
            "SELECT data, updated_count FROM daily_trending WHERE date = ? AND language = ?",
            (date_str, language)
        ).fetchone()

        existing_data = []
        updated_count = 0
        if row:
            existing_data = json.loads(row[0]) if row[0] else []
            updated_count = row[1] + 1

        # 按 full_name 合并，取最新的 stars 和 stars_delta
        existing_map = {item["full_name"]: item for item in existing_data}
        for item in items:
            full_name = item["full_name"]
            if full_name in existing_map:
                # 更新已有项目
                existing_map[full_name]["stars"] = item.get("stars", existing_map[full_name]["stars"])
                existing_map[full_name]["stars_delta"] = item.get("stars_delta", existing_map[full_name]["stars_delta"])
                existing_map[full_name]["rank"] = item.get("rank", existing_map[full_name]["rank"])
            else:
                # 新增项目
                existing_map[full_name] = item
                updated_count += 1

        # 重新排序
        merged_items = sorted(existing_map.values(), key=lambda x: x.get("rank", 999))

        # 保存
        await db.execute("""
            INSERT OR REPLACE INTO daily_trending (date, language, total_count, updated_count, summary, data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (date_str, language, len(merged_items), updated_count, summary, json.dumps(merged_items)))

        await db.commit()
        return {"date": date_str, "language": language, "total_count": len(merged_items), "updated_count": updated_count}
    finally:
        await db.close()


async def get_daily_trending(date_str: str = None, language: str = "all") -> Optional[Dict]:
    """获取某天热榜"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    db = await get_db()
    try:
        row = await db.execute(
            "SELECT * FROM daily_trending WHERE date = ? AND language = ?",
            (date_str, language)
        ).fetchone()

        if row:
            data = json.loads(row["data"]) if row["data"] else []
            return {
                "date": row["date"],
                "language": row["language"],
                "total_count": row["total_count"],
                "updated_count": row["updated_count"],
                "summary": row["summary"],
                "items": data
            }
        return None
    finally:
        await db.close()


async def get_available_dates(language: str = "all") -> List[str]:
    """获取有数据的日期列表"""
    db = await get_db()
    try:
        rows = await db.execute(
            "SELECT DISTINCT date FROM daily_trending WHERE language = ? ORDER BY date DESC",
            (language,)
        ).fetchall()
        return [row["date"] for row in rows]
    finally:
        await db.close()


# ── 仓库操作 ──


async def search_repos(keyword: str, limit: int = 20) -> List[Dict]:
    """搜索项目"""
    db = await get_db()
    try:
        rows = await db.execute("""
            SELECT * FROM repos
            WHERE full_name LIKE ? OR name LIKE ? OR description LIKE ?
            ORDER BY stars DESC LIMIT ?
        """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_repo(full_name: str) -> Optional[Dict]:
    """获取项目详情"""
    db = await get_db()
    try:
        row = await db.execute(
            "SELECT * FROM repos WHERE full_name = ?", (full_name,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_repo_trend(full_name: str) -> List[Dict]:
    """获取项目趋势"""
    db = await get_db()
    try:
        rows = await db.execute("""
            SELECT rh.* FROM repo_history rh
            JOIN repos r ON rh.repo_id = r.id
            WHERE r.full_name = ?
            ORDER BY rh.date DESC
            LIMIT 30
        """, (full_name,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def upsert_repo(item: Dict):
    """更新或插入项目"""
    db = await get_db()
    try:
        full_name = item["full_name"]
        now = datetime.now().strftime("%Y-%m-%d")

        # 检查是否存在
        row = await db.execute(
            "SELECT id, first_seen, appearances FROM repos WHERE full_name = ?", (full_name,)
        ).fetchone()

        if row:
            # 更新
            await db.execute("""
                UPDATE repos SET
                    stars = ?, forks = ?, description = ?, language = ?,
                    last_seen = ?, appearances = ?
                WHERE full_name = ?
            """, (
                item.get("stars", 0), item.get("forks", 0),
                item.get("description"), item.get("language"),
                now, row["appearances"] + 1, full_name
            ))
        else:
            # 插入
            await db.execute("""
                INSERT INTO repos (full_name, owner, name, url, description, language, stars, forks, first_seen, last_seen, appearances)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                full_name, item.get("owner"), item.get("name"),
                item.get("url"), item.get("description"), item.get("language"),
                item.get("stars", 0), item.get("forks", 0),
                now, now
            ))

        await db.commit()
    finally:
        await db.close()


# ── 订阅操作 ──


async def get_subscriptions() -> List[Dict]:
    """获取订阅列表"""
    db = await get_db()
    try:
        rows = await db.execute("SELECT * FROM subscriptions ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def add_subscription(target: str) -> Dict:
    """添加订阅"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO subscriptions (target) VALUES (?)", (target,)
        )
        await db.commit()
        return {"id": cursor.lastrowid, "target": target}
    finally:
        await db.close()


async def delete_subscription(subscription_id: int) -> bool:
    """删除订阅"""
    db = await get_db()
    try:
        await db.execute("DELETE FROM subscriptions WHERE id = ?", (subscription_id,))
        await db.commit()
        return True
    finally:
        await db.close()


async def update_subscription(subscription_id: int, enabled: bool = None, notify_enabled: bool = None) -> bool:
    """更新订阅"""
    db = await get_db()
    try:
        if enabled is not None:
            await db.execute("UPDATE subscriptions SET enabled = ? WHERE id = ?", (enabled, subscription_id))
        if notify_enabled is not None:
            await db.execute("UPDATE subscriptions SET notify_enabled = ? WHERE id = ?", (notify_enabled, subscription_id))
        await db.commit()
        return True
    finally:
        await db.close()


# ── 监控动态操作 ──


async def upload_monitor_events(repo: str, repo_info: Dict, events: List[Dict]):
    """上传监控数据"""
    db = await get_db()
    try:
        # 更新仓库缓存
        await db.execute("""
            INSERT OR REPLACE INTO watched_repos
            (full_name, stars, forks, open_issues, language, description, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            repo, repo_info.get("stars", 0), repo_info.get("forks", 0),
            repo_info.get("open_issues", 0), repo_info.get("language"),
            repo_info.get("description")
        ))

        # 获取订阅 ID
        row = await db.execute(
            "SELECT id FROM subscriptions WHERE target = ?", (repo,)
        ).fetchone()
        subscription_id = row["id"] if row else None

        # 插入动态
        for event in events:
            await db.execute("""
                INSERT INTO monitor_events
                (subscription_id, repo_name, event_type, title, body, url, version, event_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                subscription_id, repo, event.get("type"),
                event.get("title"), event.get("body"),
                event.get("url"), event.get("version"),
                event.get("time")
            ))

        await db.commit()
        return {"repo": repo, "events_count": len(events)}
    finally:
        await db.close()


async def get_monitor_events(repo: str = None, limit: int = 50) -> List[Dict]:
    """获取监控动态"""
    db = await get_db()
    try:
        if repo:
            rows = await db.execute("""
                SELECT me.*, wr.stars, wr.forks FROM monitor_events me
                LEFT JOIN watched_repos wr ON me.repo_name = wr.full_name
                WHERE me.repo_name = ?
                ORDER BY me.event_time DESC LIMIT ?
            """, (repo, limit)).fetchall()
        else:
            rows = await db.execute("""
                SELECT me.*, wr.stars, wr.forks FROM monitor_events me
                LEFT JOIN watched_repos wr ON me.repo_name = wr.full_name
                ORDER BY me.event_time DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# ── 分析报告操作 ──


async def upload_report(date_str: str, report_type: str, content: Dict, source: str = "llm") -> Dict:
    """上传分析报告"""
    db = await get_db()
    try:
        cursor = await db.execute("""
            INSERT INTO reports (date, type, source, content)
            VALUES (?, ?, ?, ?)
        """, (date_str, report_type, source, json.dumps(content)))
        await db.commit()
        return {"id": cursor.lastrowid, "date": date_str, "type": report_type}
    finally:
        await db.close()


async def get_reports(date_str: str = None, limit: int = 30) -> List[Dict]:
    """获取报告列表"""
    db = await get_db()
    try:
        if date_str:
            rows = await db.execute("""
                SELECT * FROM reports WHERE date = ? ORDER BY created_at DESC LIMIT ?
            """, (date_str, limit)).fetchall()
        else:
            rows = await db.execute("""
                SELECT * FROM reports ORDER BY date DESC, created_at DESC LIMIT ?
            """, (limit,)).fetchall()
        result = []
        for row in rows:
            r = dict(row)
            r["content"] = json.loads(row["content"]) if row["content"] else {}
            result.append(r)
        return result
    finally:
        await db.close()


async def get_report(report_id: int) -> Optional[Dict]:
    """获取报告详情"""
    db = await get_db()
    try:
        row = await db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if row:
            r = dict(row)
            r["content"] = json.loads(row["content"]) if row["content"] else {}
            return r
        return None
    finally:
        await db.close()
