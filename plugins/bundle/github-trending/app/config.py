"""GitHub Trend Hub 配置

env_prefix=GITHUB_TRENDING_ 避免与全局 / 其他插件的 HOST/PORT/DATA_DIR
撞名。需要覆盖时直接 export 即可：

    export GITHUB_TRENDING_PORT=8901
    export GITHUB_TRENDING_DATA_DIR=/var/lib/qwenpaw/data
    export GITHUB_TRENDING_COLLECT_LANGUAGES='["", "python", "go"]'   # JSON
    export GITHUB_TRENDING_COLLECT_LANGUAGES=',python,go'              # CSV
"""

import json
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> str:
    return str(Path.home() / ".qwenpaw" / "data")


# collector 默认抓取的语言列表:空串 = github.com/trending(全部)
_DEFAULT_LANGUAGES: List[str] = [
    "", "python", "go", "rust", "typescript", "javascript", "java", "html",
]


def _parse_languages(raw: str) -> List[str]:
    """把 collect_languages 字段值(可能是 JSON 字符串 / 逗号分隔)归一化为 list[str]。

    - JSON 数组字符串:json.loads
    - 逗号分隔:`a,b,c` → ["a","b","c"];允许空段以表示 "all"(` ,python` → ["", "python"])
    - 空 / 不识别:fallback 到默认
    """
    if isinstance(raw, list):
        return [str(x) for x in raw]
    if not isinstance(raw, str):
        return list(_DEFAULT_LANGUAGES)
    s = raw.strip()
    if not s:
        return list(_DEFAULT_LANGUAGES)
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            pass
    # 逗号分隔;空段保留(代表 "all")
    return [p.strip() if p != "" else "" for p in s.split(",")]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GITHUB_TRENDING_",
        extra="ignore",
    )

    # ── Server ──
    host: str = "127.0.0.1"
    port: int = 7901
    data_dir: str = _default_data_dir()
    # 缺省值在属性层计算,这样在覆盖 data_dir 后 db_path 会自动跟随。
    db_path: str = ""

    # ── Collector ──
    collect_enabled: bool = True
    # 采集周期(分钟)。每小时一次 = 60
    collect_interval_min: int = 60
    # GitHub Trending 周期参数(daily / weekly / monthly)
    collect_period: str = "daily"
    # 抓取的语言列表。空串代表"all"(github.com/trending)
    # 类型是 str:env 永远是字符串,自己在 _parse_languages 里支持 JSON / CSV 两种写法
    collect_languages: str = ",".join(_DEFAULT_LANGUAGES)
    # 可选:GitHub PAT。HTML 抓取不需要;留作将来切到 GitHub Search API 时用。
    github_token: str = ""

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        # db_path 缺省时跟随 data_dir
        if not self.db_path:
            object.__setattr__(
                self,
                "db_path",
                str(Path(self.data_dir) / "github-trending.db"),
            )
        # collect_languages 归一化为 list[str](放回同名属性)
        parsed = _parse_languages(self.collect_languages)
        object.__setattr__(self, "collect_languages", parsed)


settings = Settings()
