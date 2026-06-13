from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Subscription:
    name: str
    rss_path: str


@dataclass
class Alert:
    """系统告警"""
    key: str           # 告警唯一标识，如 "COOKIE_EXPIRED"
    title: str         # 告警标题
    message: str       # 告警详情
    level: str = "error"  # error / warning / info
    error_code: int = 0   # 相关错误码


@dataclass
class FetchResult:
    """fetch_all_feeds 的返回结果"""
    articles: list = field(default_factory=list)  # list[Article]
    alerts: list = field(default_factory=list)     # list[Alert]


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
