import os
import tempfile
from unittest.mock import MagicMock, patch

from app.config import AppConfig
from app.scheduler import create_sync_job, create_digest_job


class TestSchedulerJobs:
    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.fetch_all_feeds")
    @patch("app.scheduler.scrape_article")
    @patch("app.scheduler.TruncateSummarizer")
    @patch("app.scheduler.AlertManager")
    def test_sync_job_filters_existing_articles(
        self, mock_alert_cls, mock_summarizer_cls, mock_scrape, mock_fetch, mock_repo_cls
    ):
        from app.models import Article, FetchResult

        mock_repo = MagicMock()
        mock_repo.exists_by_url.return_value = True
        mock_repo_cls.return_value = mock_repo

        mock_fetch.return_value = FetchResult(
            articles=[Article(title="旧文章", article_url="https://old.com", author="公众号")],
            alerts=[],
        )

        mock_summarizer = MagicMock()
        mock_summarizer.summarize.return_value = "摘要"
        mock_summarizer_cls.return_value = mock_summarizer

        config = AppConfig()
        sync_job = create_sync_job(config)
        sync_job()

        mock_scrape.assert_not_called()

    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.fetch_all_feeds")
    @patch("app.scheduler.scrape_article")
    @patch("app.scheduler.TruncateSummarizer")
    @patch("app.scheduler.AlertManager")
    def test_sync_job_scrapes_new_articles(
        self, mock_alert_cls, mock_summarizer_cls, mock_scrape, mock_fetch, mock_repo_cls
    ):
        from app.models import Article, FetchResult

        mock_repo = MagicMock()
        mock_repo.exists_by_url.return_value = False
        mock_repo.save.return_value = 1
        mock_repo_cls.return_value = mock_repo

        mock_fetch.return_value = FetchResult(
            articles=[Article(title="新文章", article_url="https://new.com", author="公众号")],
            alerts=[],
        )

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8") as f:
            f.write("# 测试文章\n\n这是文章内容。")
            tmp_md_path = f.name

        try:
            mock_scrape.return_value = {
                "markdown_path": tmp_md_path,
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
        finally:
            os.unlink(tmp_md_path)

    @patch("app.scheduler.ArticleRepository")
    @patch("app.notifier.email.EmailNotifier")
    def test_digest_job_sends_email(self, mock_notifier_cls, mock_repo_cls):
        from app.models import Article

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
        config.notifier.email.recipients = ["test@example.com"]
        digest_job = create_digest_job(config)
        digest_job()

        mock_notifier.send.assert_called_once()

    @patch("app.scheduler.ArticleRepository")
    @patch("app.notifier.email.EmailNotifier")
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

    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.fetch_all_feeds")
    @patch("app.scheduler.AlertManager")
    def test_sync_job_sends_cookie_alert(self, mock_alert_cls, mock_fetch, mock_repo_cls):
        from app.models import Article, FetchResult, Alert

        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo

        # 模拟 Cookie 过期告警
        alert = Alert(key="COOKIE_EXPIRED", title="Cookie过期", message="error", error_code=200013)
        mock_fetch.return_value = FetchResult(articles=[], alerts=[alert])

        mock_alert_manager = MagicMock()
        mock_alert_cls.return_value = mock_alert_manager

        config = AppConfig()
        config.subscriptions = []
        sync_job = create_sync_job(config)
        sync_job()

        mock_alert_manager.send_cookie_expired_alert.assert_called_once()

    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.fetch_all_feeds")
    @patch("app.scheduler.AlertManager")
    def test_sync_job_sends_rsshub_alert(self, mock_alert_cls, mock_fetch, mock_repo_cls):
        from app.models import FetchResult, Alert

        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_fetch

        # 模拟 RSSHub 不可达告警
        alert = Alert(key="RSSHUB_UNREACHABLE", title="RSSHub不可达", message="error")
        mock_fetch.return_value = FetchResult(articles=[], alerts=[alert])

        mock_alert_manager = MagicMock()
        mock_alert_cls.return_value = mock_alert_manager

        config = AppConfig()
        config.subscriptions = []
        sync_job = create_sync_job(config)
        sync_job()

        mock_alert_manager.send_rsshub_down_alert.assert_called_once()
