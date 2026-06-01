"""GitHub Trend Hub 配置"""

import os
from pathlib import Path


class Settings:
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "7901"))
    data_dir: str = os.getenv("DATA_DIR", str(Path(__file__).parent.parent / "data"))
    db_path: str = os.getenv("DB_PATH", str(Path(data_dir) / "trending.db"))


settings = Settings()
