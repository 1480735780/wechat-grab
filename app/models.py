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
