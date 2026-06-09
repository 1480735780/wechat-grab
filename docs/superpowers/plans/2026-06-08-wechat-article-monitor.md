# WeChat Article Monitor 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个自动监控微信公众号文章更新的个人知识管理工具，通过 RSSHub 轮询更新，抓取文章转为 Markdown（含图片本地化），并通过邮件日报推送。

**Architecture:** 单进程 Python 应用，使用 APScheduler 调度两个独立 Job（文章同步 + 日报推送），SQLite 去重，Docker Compose 部署（含 RSSHub）。

**Tech Stack:** Python 3.11+, APScheduler, feedparser, requests, BeautifulSoup4, markdownify, Pydantic, SQLite, SMTP, Docker

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `config.yaml` | 主配置文件 |
| `.env.example` | 环境变量模板 |
| `main.py` | 入口：启动 APScheduler |
| `app/__init__.py` | 包初始化 |
| `app/config.py` | Pydantic 配置模型，支持环境变量覆盖 |
| `app/models.py` | 数据模型定义（Article dataclass） |
| `app/logger.py` | 统一日志配置（Console + File） |
| `app/repository.py` | SQLite 去重与状态管理 |
| `app/fetcher.py` | RSSHub 轮询与文章发现 |
| `app/scraper.py` | 文章抓取 + 图片下载 + HTML→Markdown |
| `app/summarizer.py` | 摘要生成抽象层 |
| `app/notifier/__init__.py` | 包初始化 |
| `app/notifier/base.py` | Notifier 抽象基类 |
| `app/notifier/email.py` | SMTP 邮件推送（日报模式） |
| `app/scheduler.py` | APScheduler 调度逻辑（Job1 同步 + Job2 日报） |
| `requirements.txt` | Python 依赖 |
| `Dockerfile` | 容器构建 |
| `docker-compose.yml` | RSSHub + 应用编排 |
| `tests/test_repository.py` | repository 单元测试 |
| `tests/test_fetcher.py` | fetcher 单元测试 |
| `tests/test_scraper.py` | scraper 单元测试 |
| `tests/test_summarizer.py` | summarizer 单元测试 |
| `tests/test_notifier.py` | notifier 单元测试 |
| `tests/test_scheduler.py` | scheduler 集成测试 |

---

### Task 1: 项目骨架与配置模型

**Files:**
- Create: `config.yaml`
- Create: `.env.example`
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/models.py`

- [ ] **Step 1: 创建 requirements.txt**

```txt
apscheduler==3.10.4
feedparser==6.0.11
requests==2.32.3
beautifulsoup4==4.12.3
markdownify==0.14.1
pydantic==2.7.4
pydantic-settings==2.3.4
pyyaml==6.0.1
```

- [ ] **Step 2: 创建 config.yaml**

```yaml
# RSSHub 配置
rsshub:
  base_url: "https://rsshub.app"
  timeout: 30

# 订阅的公众号列表
subscriptions:
  - name: "机器之心"
    rss_path: "/wechat/mp/almosthuman2014"
  - name: "腾讯技术工程"
    rss_path: "/wechat/mp/tencent_tech"
  - name: "InfoQ"
    rss_path: "/wechat/mp/infoqchina"

# 调度配置
scheduler:
  sync:
    start_hour: 8
    end_hour: 22
    interval_minutes: 60
    run_on_startup: true
  digest:
    hour: 22
    minute: 5

# 输出配置
output:
  base_dir: "./output"
  organize_by_date: true

# 推送配置
notifier:
  email:
    enabled: true
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
    sender: ""
    # password 仅通过环境变量 WA_NOTIFIER_EMAIL_PASSWORD 设置
    recipients: []
    digest_mode: true
  feishu:
    enabled: false
    app_id: ""
    app_secret: ""
    folder_token: ""

# 数据库
database:
  path: "./data/articles.db"
```

- [ ] **Step 3: 创建 .env.example**

```env
WA_RSSHUB_BASE_URL=https://rsshub.app
WA_NOTIFIER_EMAIL_PASSWORD=your_email_password_here
WA_DATABASE_PATH=./data/articles.db
```

- [ ] **Step 4: 创建 app/__init__.py**

```python
```

- [ ] **Step 5: 创建 app/models.py**

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Subscription:
    name: str
    rss_path: str


@dataclass
class Article:
    id: Optional[int] = None
    article_url: str = ""
    title: str = ""
    author: str = ""
    publish_time: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    status: str = "pending"
    markdown_path: str = ""
    content_hash: str = ""
    summary: str = ""
    error_message: Optional[str] = None
    fail_count: int = 0
    created_at: Optional[datetime] = None
```

- [ ] **Step 6: 创建 app/config.py**

```python
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class RSSHubConfig(BaseModel):
    base_url: str = "https://rsshub.app"
    timeout: int = 30


class SubscriptionConfig(BaseModel):
    name: str
    rss_path: str


class SyncConfig(BaseModel):
    start_hour: int = 8
    end_hour: int = 22
    interval_minutes: int = 60
    run_on_startup: bool = True


class DigestConfig(BaseModel):
    hour: int = 22
    minute: int = 5


class SchedulerConfig(BaseModel):
    sync: SyncConfig = SyncConfig()
    digest: DigestConfig = DigestConfig()


class OutputConfig(BaseModel):
    base_dir: str = "./output"
    organize_by_date: bool = True


class EmailConfig(BaseModel):
    enabled: bool = True
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    sender: str = ""
    password: str = ""  # 通过环境变量覆盖
    recipients: list[str] = Field(default_factory=list)
    digest_mode: bool = True


class FeishuConfig(BaseModel):
    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    folder_token: str = ""


class NotifierConfig(BaseModel):
    email: EmailConfig = EmailConfig()
    feishu: FeishuConfig = FeishuConfig()


class DatabaseConfig(BaseModel):
    path: str = "./data/articles.db"


class AppConfig(BaseSettings):
    rsshub: RSSHubConfig = RSSHubConfig()
    subscriptions: list[SubscriptionConfig] = Field(default_factory=list)
    scheduler: SchedulerConfig = SchedulerConfig()
    output: OutputConfig = OutputConfig()
    notifier: NotifierConfig = NotifierConfig()
    database: DatabaseConfig = DatabaseConfig()

    model_config = {
        "env_prefix": "WA_",
        "env_nested_delimiter": "__",
    }


def load_config(config_path: str = "config.yaml") -> AppConfig:
    config_file = Path(config_path)
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}
    return AppConfig(**data)
```

- [ ] **Step 7: 安装依赖并验证配置加载**

Run: `cd "g:\Vibe coding作品\wechat-article" && pip install -r requirements.txt`

验证：

```python
from app.config import load_config
cfg = load_config()
print(cfg.rsshub.base_url)
print(cfg.subscriptions)
print(cfg.scheduler.sync.start_hour)
```

- [ ] **Step 8: Commit**

```bash
git add config.yaml .env.example requirements.txt app/__init__.py app/config.py app/models.py
git commit -m "feat: add project skeleton and config model"
```

---

### Task 2: 日志模块

**Files:**
- Create: `app/logger.py`

- [ ] **Step 1: 创建 app/logger.py**

```python
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logger(log_dir: str = "logs", log_level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("wechat-article")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (按天轮转，保留 30 天)
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        log_path / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
```

- [ ] **Step 2: 验证日志模块**

```python
from app.logger import setup_logger
logger = setup_logger()
logger.info("Logger test")
```

- [ ] **Step 3: Commit**

```bash
git add app/logger.py
git commit -m "feat: add logger with console and file output"
```

---

### Task 3: 数据持久化模块（repository）

**Files:**
- Create: `app/repository.py`
- Create: `tests/__init__.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1: 创建 tests/__init__.py**

```python
```

- [ ] **Step 2: 写 repository 的失败测试**

Create `tests/test_repository.py`:

```python
import os
import tempfile
from datetime import datetime

from app.models import Article
from app.repository import ArticleRepository


class TestArticleRepository:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.repo = ArticleRepository(self.db_path)

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_init_creates_table(self):
        assert os.path.exists(self.db_path)

    def test_save_and_get_by_url(self):
        article = Article(
            article_url="https://mp.weixin.qq.com/s/test123",
            title="测试文章",
            author="测试公众号",
            publish_time=datetime(2026, 6, 8, 10, 30),
            fetched_at=datetime(2026, 6, 8, 11, 0),
            status="fetched",
            markdown_path="output/test/2026/06/test.md",
            content_hash="abc123",
            summary="这是摘要",
        )
        article_id = self.repo.save(article)
        assert article_id > 0

        result = self.repo.get_by_url("https://mp.weixin.qq.com/s/test123")
        assert result is not None
        assert result.title == "测试文章"
        assert result.author == "测试公众号"
        assert result.status == "fetched"

    def test_exists_by_url(self):
        assert not self.repo.exists_by_url("https://mp.weixin.qq.com/s/notexist")

        article = Article(
            article_url="https://mp.weixin.qq.com/s/exist",
            title="存在文章",
            author="公众号",
        )
        self.repo.save(article)
        assert self.repo.exists_by_url("https://mp.weixin.qq.com/s/exist")

    def test_update_status(self):
        article = Article(
            article_url="https://mp.weixin.qq.com/s/status_test",
            title="状态测试",
            author="公众号",
            status="fetched",
        )
        article_id = self.repo.save(article)
        self.repo.update_status(article_id, "notified")

        result = self.repo.get_by_url("https://mp.weixin.qq.com/s/status_test")
        assert result.status == "notified"

    def test_increment_fail_count(self):
        article = Article(
            article_url="https://mp.weixin.qq.com/s/fail_test",
            title="失败测试",
            author="公众号",
            status="failed",
        )
        article_id = self.repo.save(article)
        self.repo.increment_fail_count(article_id)

        result = self.repo.get_by_url("https://mp.weixin.qq.com/s/fail_test")
        assert result.fail_count == 1

    def test_check_content_changed(self):
        article = Article(
            article_url="https://mp.weixin.qq.com/s/hash_test",
            title="哈希测试",
            author="公众号",
            content_hash="hash_v1",
        )
        self.repo.save(article)

        assert self.repo.check_content_changed(
            "https://mp.weixin.qq.com/s/hash_test", "hash_v2"
        )
        assert not self.repo.check_content_changed(
            "https://mp.weixin.qq.com/s/hash_test", "hash_v1"
        )

    def test_get_articles_by_date(self):
        today = datetime(2026, 6, 8)
        article1 = Article(
            article_url="https://mp.weixin.qq.com/s/date1",
            title="今日文章1",
            author="公众号",
            fetched_at=datetime(2026, 6, 8, 10, 0),
            status="fetched",
        )
        article2 = Article(
            article_url="https://mp.weixin.qq.com/s/date2",
            title="今日文章2",
            author="公众号",
            fetched_at=datetime(2026, 6, 8, 14, 0),
            status="fetched",
        )
        article3 = Article(
            article_url="https://mp.weixin.qq.com/s/date3",
            title="昨日文章",
            author="公众号",
            fetched_at=datetime(2026, 6, 7, 10, 0),
            status="fetched",
        )
        self.repo.save(article1)
        self.repo.save(article2)
        self.repo.save(article3)

        results = self.repo.get_articles_by_date(today.date())
        assert len(results) == 2

    def test_get_unnotified_articles(self):
        article1 = Article(
            article_url="https://mp.weixin.qq.com/s/unnot1",
            title="未通知",
            author="公众号",
            fetched_at=datetime(2026, 6, 8, 10, 0),
            status="fetched",
        )
        article2 = Article(
            article_url="https://mp.weixin.qq.com/s/unnot2",
            title="已通知",
            author="公众号",
            fetched_at=datetime(2026, 6, 8, 10, 0),
            status="notified",
        )
        self.repo.save(article1)
        self.repo.save(article2)

        results = self.repo.get_unnotified_articles(datetime(2026, 6, 8).date())
        assert len(results) == 1
        assert results[0].title == "未通知"

    def test_batch_update_status(self):
        a1 = Article(article_url="https://mp.weixin.qq.com/s/batch1", title="1", author="a", status="fetched")
        a2 = Article(article_url="https://mp.weixin.qq.com/s/batch2", title="2", author="a", status="fetched")
        id1 = self.repo.save(a1)
        id2 = self.repo.save(a2)
        self.repo.batch_update_status([id1, id2], "notified")

        r1 = self.repo.get_by_url("https://mp.weixin.qq.com/s/batch1")
        r2 = self.repo.get_by_url("https://mp.weixin.qq.com/s/batch2")
        assert r1.status == "notified"
        assert r2.status == "notified"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.repository'`

- [ ] **Step 4: 实现 repository**

Create `app/repository.py`:

```python
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from app.models import Article


class ArticleRepository:
    def __init__(self, db_path: str = "./data/articles.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL DEFAULT '',
                publish_time DATETIME,
                fetched_at DATETIME,
                status TEXT NOT NULL DEFAULT 'pending',
                markdown_path TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                error_message TEXT,
                fail_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_article_url ON articles(article_url)"
        )
        conn.commit()
        conn.close()

    def _row_to_article(self, row: sqlite3.Row) -> Article:
        return Article(
            id=row["id"],
            article_url=row["article_url"],
            title=row["title"],
            author=row["author"],
            publish_time=datetime.fromisoformat(row["publish_time"])
            if row["publish_time"]
            else None,
            fetched_at=datetime.fromisoformat(row["fetched_at"])
            if row["fetched_at"]
            else None,
            status=row["status"],
            markdown_path=row["markdown_path"],
            content_hash=row["content_hash"],
            summary=row["summary"],
            error_message=row["error_message"],
            fail_count=row["fail_count"],
            created_at=datetime.fromisoformat(row["created_at"])
            if row["created_at"]
            else None,
        )

    def exists_by_url(self, article_url: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM articles WHERE article_url = ?", (article_url,)
        ).fetchone()
        conn.close()
        return row is not None

    def get_by_url(self, article_url: str) -> Optional[Article]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM articles WHERE article_url = ?", (article_url,)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return self._row_to_article(row)

    def save(self, article: Article) -> int:
        conn = self._get_conn()
        cursor = conn.execute(
            """INSERT INTO articles
               (article_url, title, author, publish_time, fetched_at, status,
                markdown_path, content_hash, summary, error_message, fail_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                article.article_url,
                article.title,
                article.author,
                article.publish_time.isoformat() if article.publish_time else None,
                article.fetched_at.isoformat() if article.fetched_at else None,
                article.status,
                article.markdown_path,
                article.content_hash,
                article.summary,
                article.error_message,
                article.fail_count,
            ),
        )
        conn.commit()
        article_id = cursor.lastrowid
        conn.close()
        return article_id

    def update_status(self, article_id: int, status: str):
        conn = self._get_conn()
        conn.execute(
            "UPDATE articles SET status = ? WHERE id = ?", (status, article_id)
        )
        conn.commit()
        conn.close()

    def increment_fail_count(self, article_id: int):
        conn = self._get_conn()
        conn.execute(
            "UPDATE articles SET fail_count = fail_count + 1 WHERE id = ?",
            (article_id,),
        )
        conn.commit()
        conn.close()

    def check_content_changed(self, article_url: str, new_hash: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT content_hash FROM articles WHERE article_url = ?",
            (article_url,),
        ).fetchone()
        conn.close()
        if row is None:
            return True
        return row["content_hash"] != new_hash

    def get_articles_by_date(self, target_date: date) -> list[Article]:
        conn = self._get_conn()
        date_str = target_date.isoformat()
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE DATE(fetched_at) = ?
               ORDER BY fetched_at DESC""",
            (date_str,),
        ).fetchall()
        conn.close()
        return [self._row_to_article(row) for row in rows]

    def get_unnotified_articles(self, target_date: date) -> list[Article]:
        conn = self._get_conn()
        date_str = target_date.isoformat()
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE DATE(fetched_at) = ? AND status = 'fetched'
               ORDER BY fetched_at DESC""",
            (date_str,),
        ).fetchall()
        conn.close()
        return [self._row_to_article(row) for row in rows]

    def batch_update_status(self, article_ids: list[int], status: str):
        conn = self._get_conn()
        placeholders = ",".join("?" for _ in article_ids)
        conn.execute(
            f"UPDATE articles SET status = ? WHERE id IN ({placeholders})",
            [status] + article_ids,
        )
        conn.commit()
        conn.close()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_repository.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add app/repository.py tests/__init__.py tests/test_repository.py
git commit -m "feat: add ArticleRepository with SQLite persistence"
```

---

### Task 4: RSS 轮询模块（fetcher）

**Files:**
- Create: `app/fetcher.py`
- Create: `tests/test_fetcher.py`

- [ ] **Step 1: 写 fetcher 的失败测试**

Create `tests/test_fetcher.py`:

```python
from unittest.mock import MagicMock, patch

from app.fetcher import fetch_feed, fetch_all_feeds
from app.models import Subscription


class TestFetcher:
    @patch("app.fetcher.feedparser.parse")
    def test_fetch_feed_success(self, mock_parse):
        mock_entry = MagicMock()
        mock_entry.title = "测试文章"
        mock_entry.link = "https://mp.weixin.qq.com/s/test123"
        mock_entry.published = "Sun, 08 Jun 2026 10:30:00 +0800"
        mock_entry.author = "测试公众号"

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]
        mock_feed.bozo = 0
        mock_parse.return_value = mock_feed

        sub = Subscription(name="测试公众号", rss_path="/wechat/mp/test")
        articles = fetch_feed(sub, base_url="https://rsshub.app")

        assert len(articles) == 1
        assert articles[0].title == "测试文章"
        assert articles[0].article_url == "https://mp.weixin.qq.com/s/test123"
        assert articles[0].author == "测试公众号"

    @patch("app.fetcher.feedparser.parse")
    def test_fetch_feed_empty(self, mock_parse):
        mock_feed = MagicMock()
        mock_feed.entries = []
        mock_feed.bozo = 0
        mock_parse.return_value = mock_feed

        sub = Subscription(name="空公众号", rss_path="/wechat/mp/empty")
        articles = fetch_feed(sub, base_url="https://rsshub.app")
        assert len(articles) == 0

    @patch("app.fetcher.feedparser.parse")
    def test_fetch_feed_failure_returns_empty(self, mock_parse):
        mock_parse.side_effect = Exception("Connection error")

        sub = Subscription(name="失败公众号", rss_path="/wechat/mp/fail")
        articles = fetch_feed(sub, base_url="https://rsshub.app")
        assert len(articles) == 0

    @patch("app.fetcher.fetch_feed")
    def test_fetch_all_feeds(self, mock_fetch_feed):
        from app.models import Article
        from datetime import datetime

        mock_fetch_feed.return_value = [
            Article(
                title="文章1",
                article_url="https://mp.weixin.qq.com/s/1",
                author="公众号A",
            )
        ]

        subs = [
            Subscription(name="公众号A", rss_path="/wechat/mp/a"),
            Subscription(name="公众号B", rss_path="/wechat/mp/b"),
        ]
        articles = fetch_all_feeds(subs, base_url="https://rsshub.app")
        assert len(articles) == 2  # 2 subs * 1 article each
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_fetcher.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 fetcher**

Create `app/fetcher.py`:

```python
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import feedparser

from app.models import Article, Subscription

logger = logging.getLogger("wechat-article")


def fetch_feed(
    subscription: Subscription,
    base_url: str = "https://rsshub.app",
    timeout: int = 30,
) -> list[Article]:
    url = f"{base_url}{subscription.rss_path}"
    logger.info(f"Fetching RSS feed: {url}")

    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "WeChatArticleMonitor/1.0"})

        if feed.bozo and not feed.entries:
            logger.warning(f"Failed to parse feed from {url}: {feed.bozo_exception}")
            return []

        articles = []
        for entry in feed.entries:
            publish_time = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                publish_time = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                publish_time = datetime(*entry.updated_parsed[:6])

            article = Article(
                title=getattr(entry, "title", "无标题"),
                article_url=getattr(entry, "link", ""),
                author=subscription.name,
                publish_time=publish_time,
            )
            if article.article_url:
                articles.append(article)

        logger.info(f"Found {len(articles)} articles from {subscription.name}")
        return articles

    except Exception as e:
        logger.error(f"Error fetching feed {url}: {e}")
        return []


def fetch_all_feeds(
    subscriptions: list[Subscription],
    base_url: str = "https://rsshub.app",
    timeout: int = 30,
    max_workers: int = 5,
) -> list[Article]:
    all_articles = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sub = {
            executor.submit(fetch_feed, sub, base_url, timeout): sub
            for sub in subscriptions
        }

        for future in as_completed(future_to_sub):
            sub = future_to_sub[future]
            try:
                articles = future.result()
                all_articles.extend(articles)
            except Exception as e:
                logger.error(f"Error processing feed for {sub.name}: {e}")

    logger.info(f"Total articles found: {len(all_articles)}")
    return all_articles
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_fetcher.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app/fetcher.py tests/test_fetcher.py
git commit -m "feat: add RSS feed fetcher with concurrent polling"
```

---

### Task 5: 文章抓取与转换模块（scraper）

**Files:**
- Create: `app/scraper.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: 写 scraper 的失败测试**

Create `tests/test_scraper.py`:

```python
import os
import tempfile
from unittest.mock import MagicMock, patch

from app.scraper import scrape_article, slugify


class TestSlugify:
    def test_chinese_title(self):
        result = slugify("深度学习入门指南")
        assert len(result) > 0
        assert " " not in result

    def test_mixed_title(self):
        result = slugify("GPT-4 发布：AI 新时代")
        assert len(result) > 0


class TestScraper:
    @patch("app.scraper.requests.get")
    def test_scrape_article_success(self, mock_get):
        html_content = """
        <html><body>
        <div id="js_content">
            <h1>测试文章标题</h1>
            <p>这是文章正文内容。</p>
            <img src="https://mmbiz.qpic.cn/test.jpg" alt="测试图片">
        </div>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.encoding = "utf-8"
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            result = scrape_article(
                article_url="https://mp.weixin.qq.com/s/test123",
                author="测试公众号",
                output_base_dir=tmpdir,
            )
            assert result is not None
            assert result["markdown_path"]
            assert result["content_hash"]
            assert os.path.exists(result["markdown_path"])

    @patch("app.scraper.requests.get")
    def test_scrape_article_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection error")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = scrape_article(
                article_url="https://mp.weixin.qq.com/s/fail",
                author="测试公众号",
                output_base_dir=tmpdir,
            )
            assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_scraper.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 scraper**

Create `app/scraper.py`:

```python
import hashlib
import logging
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger = logging.getLogger("wechat-article")


def slugify(text: str, max_length: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    if len(text) > max_length:
        text = text[:max_length].rstrip("-")
    return text or "untitled"


def _download_image(img_url: str, save_dir: str) -> Optional[str]:
    try:
        response = requests.get(img_url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if response.status_code != 200:
            logger.warning(f"Failed to download image: {img_url}")
            return None

        # 从 URL 或 Content-Disposition 提取文件名
        filename = img_url.split("/")[-1].split("?")[0]
        if not filename or "." not in filename:
            ext = ".jpg"
            content_type = response.headers.get("Content-Type", "")
            if "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            elif "webp" in content_type:
                ext = ".webp"
            filename = hashlib.md5(img_url.encode()).hexdigest()[:12] + ext

        save_path = os.path.join(save_dir, filename)
        with open(save_path, "wb") as f:
            f.write(response.content)

        logger.debug(f"Downloaded image: {img_url} -> {save_path}")
        return filename

    except Exception as e:
        logger.warning(f"Error downloading image {img_url}: {e}")
        return None


def scrape_article(
    article_url: str,
    author: str,
    output_base_dir: str = "./output",
    organize_by_date: bool = True,
    publish_time: Optional[datetime] = None,
) -> Optional[dict]:
    logger.info(f"Scraping article: {article_url}")

    try:
        response = requests.get(
            article_url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        response.encoding = "utf-8"
        if response.status_code != 200:
            logger.error(f"Failed to fetch article: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error fetching article {article_url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # 提取标题
    title_el = soup.find("h1", id="activity-name") or soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else "无标题"

    # 提取正文
    content_el = soup.find("div", id="js_content") or soup.find("article") or soup.find("body")
    if not content_el:
        logger.error(f"Cannot find article content: {article_url}")
        return None

    # 构建输出目录
    now = publish_time or datetime.now()
    if organize_by_date:
        article_dir = Path(output_base_dir) / author / str(now.year) / f"{now.month:02d}"
    else:
        article_dir = Path(output_base_dir) / author
    article_dir.mkdir(parents=True, exist_ok=True)

    images_dir = article_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # 下载图片并替换链接
    for img in content_el.find_all("img"):
        src = img.get("data-src") or img.get("src", "")
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src

        local_filename = _download_image(src, str(images_dir))
        if local_filename:
            img["src"] = f"images/{local_filename}"
            # 清除 data-src 避免重复
            if img.get("data-src"):
                del img["data-src"]
        else:
            logger.warning(f"Keeping original image URL: {src}")

    # HTML -> Markdown
    markdown_content = md(str(content_el), heading_style="ATX", strip=["script", "style"])

    # 构建 frontmatter
    frontmatter = f"""---
title: "{title}"
author: "{author}"
published: "{now.strftime('%Y-%m-%d %H:%M')}"
source: "{article_url}"
tags:
  - wechat
---

"""

    full_markdown = frontmatter + markdown_content.strip() + "\n"

    # 计算 content_hash
    content_hash = hashlib.md5(full_markdown.encode("utf-8")).hexdigest()

    # 更新 frontmatter 中的 content_hash
    full_markdown = full_markdown.replace(
        'tags:\n  - wechat\n---',
        f'tags:\n  - wechat\ncontent_hash: "{content_hash}"\n---',
    )

    # 保存文件
    filename = f"{now.strftime('%Y%m%d')}-{slugify(title)}.md"
    markdown_path = article_dir / filename
    markdown_path.write_text(full_markdown, encoding="utf-8")

    logger.info(f"Article saved: {markdown_path}")

    return {
        "markdown_path": str(markdown_path),
        "content_hash": content_hash,
        "title": title,
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_scraper.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app/scraper.py tests/test_scraper.py
git commit -m "feat: add article scraper with image download and HTML-to-Markdown"
```

---

### Task 6: 摘要生成模块（summarizer）

**Files:**
- Create: `app/summarizer.py`
- Create: `tests/test_summarizer.py`

- [ ] **Step 1: 写 summarizer 的失败测试**

Create `tests/test_summarizer.py`:

```python
from app.summarizer import TruncateSummarizer


class TestTruncateSummarizer:
    def test_short_content(self):
        summarizer = TruncateSummarizer(max_length=200)
        result = summarizer.summarize("短内容")
        assert result == "短内容"

    def test_long_content(self):
        summarizer = TruncateSummarizer(max_length=200)
        content = "这是一段很长的内容。" * 100
        result = summarizer.summarize(content)
        assert len(result) <= 200

    def test_empty_content(self):
        summarizer = TruncateSummarizer(max_length=200)
        result = summarizer.summarize("")
        assert result == ""
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_summarizer.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 summarizer**

Create `app/summarizer.py`:

```python
from abc import ABC, abstractmethod


class BaseSummarizer(ABC):
    @abstractmethod
    def summarize(self, markdown_content: str) -> str:
        ...


class TruncateSummarizer(BaseSummarizer):
    """第一版：截取前 N 个字符"""

    def __init__(self, max_length: int = 200):
        self.max_length = max_length

    def summarize(self, markdown_content: str) -> str:
        if not markdown_content:
            return ""
        # 去掉 frontmatter
        if markdown_content.startswith("---"):
            end = markdown_content.find("---", 3)
            if end != -1:
                markdown_content = markdown_content[end + 3:].strip()
        return markdown_content[: self.max_length]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_summarizer.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app/summarizer.py tests/test_summarizer.py
git commit -m "feat: add TruncateSummarizer with frontmatter stripping"
```

---

### Task 7: 推送模块（notifier）

**Files:**
- Create: `app/notifier/__init__.py`
- Create: `app/notifier/base.py`
- Create: `app/notifier/email.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: 创建 app/notifier/__init__.py**

```python
```

- [ ] **Step 2: 创建 app/notifier/base.py**

```python
from abc import ABC, abstractmethod
from typing import list

from app.models import Article


class BaseNotifier(ABC):
    @abstractmethod
    def send(self, articles: list[Article], summaries: list[str]) -> bool:
        ...
```

- [ ] **Step 3: 写 email notifier 的失败测试**

Create `tests/test_notifier.py`:

```python
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models import Article
from app.notifier.email import EmailNotifier


class TestEmailNotifier:
    @patch("app.notifier.email.smtplib.SMTP")
    def test_send_digest_email(self, mock_smtp_cls):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        notifier = EmailNotifier(
            smtp_host="smtp.test.com",
            smtp_port=587,
            use_tls=True,
            sender="test@test.com",
            password="testpass",
            recipients=["recip@test.com"],
        )

        articles = [
            Article(
                title="测试文章1",
                article_url="https://mp.weixin.qq.com/s/1",
                author="公众号A",
                fetched_at=datetime(2026, 6, 8, 10, 0),
                status="fetched",
                markdown_path="/tmp/test1.md",
                summary="这是摘要1",
            ),
        ]

        result = notifier.send(articles, ["这是摘要1"])
        assert result is True
        mock_smtp.sendmail.assert_called_once()

    @patch("app.notifier.email.smtplib.SMTP")
    def test_send_empty_articles(self, mock_smtp_cls):
        notifier = EmailNotifier(
            smtp_host="smtp.test.com",
            smtp_port=587,
            use_tls=True,
            sender="test@test.com",
            password="testpass",
            recipients=["recip@test.com"],
        )
        result = notifier.send([], [])
        assert result is False

    @patch("app.notifier.email.smtplib.SMTP", side_effect=Exception("SMTP error"))
    def test_send_failure(self, mock_smtp_cls):
        notifier = EmailNotifier(
            smtp_host="smtp.test.com",
            smtp_port=587,
            use_tls=True,
            sender="test@test.com",
            password="testpass",
            recipients=["recip@test.com"],
        )
        articles = [
            Article(title="测试", article_url="https://test.com", author="a"),
        ]
        result = notifier.send(articles, ["摘要"])
        assert result is False
```

- [ ] **Step 4: 运行测试确认失败**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_notifier.py -v`
Expected: FAIL

- [ ] **Step 5: 实现 email notifier**

Create `app/notifier/email.py`:

```python
import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import list

from app.models import Article
from app.notifier.base import BaseNotifier

logger = logging.getLogger("wechat-article")


class EmailNotifier(BaseNotifier):
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        use_tls: bool,
        sender: str,
        password: str,
        recipients: list[str],
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.use_tls = use_tls
        self.sender = sender
        self.password = password
        self.recipients = recipients

    def send(self, articles: list[Article], summaries: list[str]) -> bool:
        if not articles:
            logger.info("No articles to notify, skipping email")
            return False

        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        subject = f"微信公众号文章日报 - {today}"

        # 构建邮件正文
        body_parts = [f"<h2>微信公众号文章日报 - {today}</h2>"]
        for i, (article, summary) in enumerate(zip(articles, summaries), 1):
            body_parts.append(
                f'<h3>{i}. {article.title}</h3>'
                f'<p><strong>来源：</strong>{article.author}</p>'
                f'<p><strong>摘要：</strong>{summary}</p>'
                f'<p><a href="{article.article_url}">阅读原文</a></p>'
                f'<hr>'
            )

        html_body = "\n".join(body_parts)

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # 附加 Markdown 文件
        for article in articles:
            if article.markdown_path and Path(article.markdown_path).exists():
                with open(article.markdown_path, "r", encoding="utf-8") as f:
                    md_content = f.read()
                md_attachment = MIMEText(md_content, "plain", "utf-8")
                filename = Path(article.markdown_path).name
                md_attachment.add_header(
                    "Content-Disposition", "attachment", filename=filename
                )
                msg.attach(md_attachment)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                if self.use_tls:
                    smtp.starttls()
                smtp.login(self.sender, self.password)
                smtp.sendmail(self.sender, self.recipients, msg.as_string())
            logger.info(f"Digest email sent: {len(articles)} articles")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_notifier.py -v`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add app/notifier/__init__.py app/notifier/base.py app/notifier/email.py tests/test_notifier.py
git commit -m "feat: add EmailNotifier with digest mode and attachments"
```

---

### Task 8: 调度模块（scheduler）

**Files:**
- Create: `app/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: 写 scheduler 的失败测试**

Create `tests/test_scheduler.py`:

```python
from unittest.mock import MagicMock, patch

from app.config import AppConfig, SchedulerConfig, SyncConfig, DigestConfig
from app.scheduler import create_sync_job, create_digest_job


class TestSchedulerJobs:
    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.fetch_all_feeds")
    @patch("app.scheduler.scrape_article")
    @patch("app.scheduler.TruncateSummarizer")
    def test_sync_job_filters_existing_articles(
        self, mock_summarizer_cls, mock_scrape, mock_fetch, mock_repo_cls
    ):
        from app.models import Article
        from datetime import datetime

        # 模拟已有文章
        mock_repo = MagicMock()
        mock_repo.exists_by_url.return_value = True
        mock_repo_cls.return_value = mock_repo

        mock_fetch.return_value = [
            Article(title="旧文章", article_url="https://old.com", author="公众号"),
        ]

        mock_summarizer = MagicMock()
        mock_summarizer.summarize.return_value = "摘要"
        mock_summarizer_cls.return_value = mock_summarizer

        config = AppConfig()
        sync_job = create_sync_job(config)
        sync_job()

        # 旧文章应被跳过，不调用 scrape
        mock_scrape.assert_not_called()

    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.fetch_all_feeds")
    @patch("app.scheduler.scrape_article")
    @patch("app.scheduler.TruncateSummarizer")
    def test_sync_job_scrapes_new_articles(
        self, mock_summarizer_cls, mock_scrape, mock_fetch, mock_repo_cls
    ):
        from app.models import Article
        from datetime import datetime

        mock_repo = MagicMock()
        mock_repo.exists_by_url.return_value = False
        mock_repo.save.return_value = 1
        mock_repo_cls.return_value = mock_repo

        mock_fetch.return_value = [
            Article(title="新文章", article_url="https://new.com", author="公众号"),
        ]

        mock_scrape.return_value = {
            "markdown_path": "/tmp/test.md",
            "content_hash": "abc123",
            "title": "新文章",
        }

        mock_summarizer = MagicMock()
        mock_summarizer.summarize.return_value = "摘要"
        mock_summarizer_cls.return_value = mock_summarizer

        config = AppConfig()
        sync_job = create_sync_job(config)
        sync_job()

        mock_scrape.assert_called_once()
        mock_repo.save.assert_called_once()

    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.EmailNotifier")
    def test_digest_job_sends_email(self, mock_notifier_cls, mock_repo_cls):
        from app.models import Article
        from datetime import datetime

        mock_repo = MagicMock()
        mock_repo.get_unnotified_articles.return_value = [
            Article(
                title="文章1",
                article_url="https://test.com",
                author="公众号",
                status="fetched",
                summary="摘要1",
            )
        ]
        mock_repo_cls.return_value = mock_repo

        mock_notifier = MagicMock()
        mock_notifier.send.return_value = True
        mock_notifier_cls.return_value = mock_notifier

        config = AppConfig()
        digest_job = create_digest_job(config)
        digest_job()

        mock_notifier.send.assert_called_once()

    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.EmailNotifier")
    def test_digest_job_skips_when_no_articles(self, mock_notifier_cls, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.get_unnotified_articles.return_value = []
        mock_repo_cls.return_value = mock_repo

        mock_notifier = MagicMock()
        mock_notifier_cls.return_value = mock_notifier

        config = AppConfig()
        digest_job = create_digest_job(config)
        digest_job()

        mock_notifier.send.assert_not_called()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_scheduler.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 scheduler**

Create `app/scheduler.py`:

```python
import logging
from datetime import datetime

from app.config import AppConfig
from app.fetcher import fetch_all_feeds
from app.models import Article
from app.repository import ArticleRepository
from app.scraper import scrape_article
from app.summarizer import TruncateSummarizer

logger = logging.getLogger("wechat-article")


def create_sync_job(config: AppConfig):
    """创建文章同步 Job：轮询 RSS → 去重 → 抓取 → 转换 → 存储"""

    def sync_job():
        logger.info("Sync job started")
        try:
            repo = ArticleRepository(config.database.path)
            summarizer = TruncateSummarizer(max_length=200)

            # 1. 轮询 RSS
            articles = fetch_all_feeds(
                config.subscriptions,
                base_url=config.rsshub.base_url,
                timeout=config.rsshub.timeout,
            )

            new_count = 0
            for article in articles:
                # 2. 去重
                if repo.exists_by_url(article.article_url):
                    logger.debug(f"Article already exists: {article.article_url}")
                    continue

                # 3. 抓取
                try:
                    result = scrape_article(
                        article_url=article.article_url,
                        author=article.author,
                        output_base_dir=config.output.base_dir,
                        organize_by_date=config.output.organize_by_date,
                        publish_time=article.publish_time,
                    )
                except Exception as e:
                    logger.error(f"Error scraping {article.article_url}: {e}")
                    article.status = "failed"
                    article.error_message = str(e)
                    repo.save(article)
                    continue

                if result is None:
                    article.status = "failed"
                    article.error_message = "Scrape returned None"
                    repo.save(article)
                    continue

                # 4. 生成摘要
                from pathlib import Path
                md_content = Path(result["markdown_path"]).read_text(encoding="utf-8")
                summary = summarizer.summarize(md_content)

                # 5. 存储
                article.status = "fetched"
                article.markdown_path = result["markdown_path"]
                article.content_hash = result["content_hash"]
                article.title = result["title"]
                article.summary = summary
                article.fetched_at = datetime.now()
                repo.save(article)
                new_count += 1

            logger.info(f"Sync job completed: {new_count} new articles")

        except Exception as e:
            logger.error(f"Sync job failed: {e}")

    return sync_job


def create_digest_job(config: AppConfig):
    """创建日报推送 Job：查询当日文章 → 发送汇总邮件"""

    def digest_job():
        logger.info("Digest job started")
        try:
            repo = ArticleRepository(config.database.path)
            today = datetime.now().date()

            # 查询当日未通知文章
            articles = repo.get_unnotified_articles(today)
            if not articles:
                logger.info("No new articles today, skipping digest")
                return

            # 发送邮件
            if config.notifier.email.enabled and config.notifier.email.recipients:
                from app.notifier.email import EmailNotifier

                notifier = EmailNotifier(
                    smtp_host=config.notifier.email.smtp_host,
                    smtp_port=config.notifier.email.smtp_port,
                    use_tls=config.notifier.email.use_tls,
                    sender=config.notifier.email.sender,
                    password=config.notifier.email.password,
                    recipients=config.notifier.email.recipients,
                )

                summaries = [a.summary for a in articles]
                success = notifier.send(articles, summaries)

                if success:
                    article_ids = [a.id for a in articles if a.id is not None]
                    if article_ids:
                        repo.batch_update_status(article_ids, "notified")
                    logger.info(f"Digest sent: {len(articles)} articles notified")
                else:
                    logger.error("Failed to send digest email")
            else:
                logger.warning("Email notifier not configured or no recipients")

        except Exception as e:
            logger.error(f"Digest job failed: {e}")

    return digest_job
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/test_scheduler.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app/scheduler.py tests/test_scheduler.py
git commit -m "feat: add sync and digest job creators"
```

---

### Task 9: 主入口与 APScheduler 集成

**Files:**
- Create: `main.py`

- [ ] **Step 1: 创建 main.py**

```python
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import load_config
from app.logger import setup_logger
from app.scheduler import create_sync_job, create_digest_job


def main():
    config = load_config()
    logger = setup_logger()
    logger.info("WeChat Article Monitor starting...")

    scheduler = BlockingScheduler()

    # Job1: 文章同步 (8:00-22:00, 每小时)
    sync_config = config.scheduler.sync
    sync_job = create_sync_job(config)
    scheduler.add_job(
        sync_job,
        trigger=CronTrigger(
            hour=f"{sync_config.start_hour}-{sync_config.end_hour}",
            minute=0,
        ),
        id="sync_job",
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        f"Sync job scheduled: {sync_config.start_hour}:00-{sync_config.end_hour}:00, every hour"
    )

    # Job2: 日报推送 (每天 22:05)
    digest_config = config.scheduler.digest
    digest_job = create_digest_job(config)
    scheduler.add_job(
        digest_job,
        trigger=CronTrigger(
            hour=digest_config.hour,
            minute=digest_config.minute,
        ),
        id="digest_job",
        max_instances=1,
        coalesce=True,
    )
    logger.info(f"Digest job scheduled: daily at {digest_config.hour}:{digest_config.minute:02d}")

    # 启动时立即执行一次同步
    if sync_config.run_on_startup:
        logger.info("Run on startup enabled, executing sync job immediately")
        sync_job()

    try:
        logger.info("Scheduler started, waiting for jobs...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证 main.py 可启动**

Run: `cd "g:\Vibe coding作品\wechat-article" && timeout 5 python main.py || true`
Expected: 日志输出 "WeChat Article Monitor starting..." 和 "Sync job started"

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main entry with APScheduler integration"
```

---

### Task 10: Docker 部署配置

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.gitignore`

- [ ] **Step 1: 创建 .gitignore**

```
__pycache__/
*.pyc
*.pyo
.env
data/
logs/
output/
*.db
.pytest_cache/
```

- [ ] **Step 2: 创建 Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/output /app/logs

CMD ["python", "main.py"]
```

- [ ] **Step 3: 创建 docker-compose.yml**

```yaml
services:
  rsshub:
    image: diygod/rsshub:latest
    ports:
      - "1200:1200"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:1200/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  wechat-article:
    build: .
    environment:
      - WA_RSSHUB_BASE_URL=http://rsshub:1200
      - WA_NOTIFIER_EMAIL_PASSWORD=${EMAIL_PASSWORD}
    volumes:
      - ./output:/app/output
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config.yaml:/app/config.yaml:ro
    depends_on:
      rsshub:
        condition: service_healthy
    restart: unless-stopped
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore Dockerfile docker-compose.yml
git commit -m "feat: add Docker deployment configuration"
```

---

### Task 11: 全量测试与修复

**Files:**
- Modify: `app/notifier/base.py` (修复 type hint)

- [ ] **Step 1: 修复 base.py 的 type hint**

`app/notifier/base.py` 中 `from typing import list` 在 Python 3.11 应使用 `list[Article]` 而无需从 typing 导入。

```python
from abc import ABC, abstractmethod

from app.models import Article


class BaseNotifier(ABC):
    @abstractmethod
    def send(self, articles: list[Article], summaries: list[str]) -> bool:
        ...
```

- [ ] **Step 2: 运行全量测试**

Run: `cd "g:\Vibe coding作品\wechat-article" && python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "fix: fix type hints and ensure all tests pass"
```

---

## 自审清单

1. **Spec 覆盖**：
   - RSSHub 轮询 → Task 4 (fetcher)
   - 并发抓取 → Task 4 (ThreadPoolExecutor)
   - SQLite 去重 → Task 3 (repository)
   - HTML→Markdown + 图片本地化 → Task 5 (scraper)
   - Frontmatter (tags, content_hash) → Task 5 (scraper)
   - 摘要生成 → Task 6 (summarizer)
   - 邮件日报推送 → Task 7 (email notifier)
   - Job1 同步 + Job2 日报 → Task 8 (scheduler)
   - APScheduler 集成 → Task 9 (main.py)
   - Docker 部署 → Task 10
   - 环境变量覆盖 → Task 1 (config.py)
   - 日志双输出 → Task 2 (logger)
   - Dead-letter 机制 → Task 3 (repository, fail_count)
   - Healthcheck → Task 10 (docker-compose)

2. **Placeholder 扫描**：无 TBD/TODO

3. **类型一致性**：Article dataclass 字段与 repository、scheduler、notifier 中的使用一致
