from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class RSSHubConfig(BaseModel):
    base_url: str = "http://localhost:1200"
    timeout: int = 30


class MPConfig(BaseModel):
    """微信公众平台接口配置（优先于 RSSHub）"""
    cookie: str = ""    # 通过环境变量 WA_MP__COOKIE 设置
    token: str = ""     # 通过环境变量 WA_MP__TOKEN 设置


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
    mp: MPConfig = MPConfig()
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
