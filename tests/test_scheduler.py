from unittest.mock import MagicMock, patch

from app.config import AppConfig
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

        existing_article = Article(
            id=1, title="旧文章", article_url="https://old.com",
            author="公众号", status="fetched", content_hash="abc",
        )

        mock_repo = MagicMock()
        mock_repo.get_by_url.return_value = existing_article
        mock_repo_cls.return_value = mock_repo

        mock_fetch.return_value = [
            Article(title="旧文章", article_url="https://old.com", author="公众号"),
        ], False

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
    @patch("app.scheduler.Path")
    def test_sync_job_scrapes_new_articles(
        self, mock_path_cls, mock_summarizer_cls, mock_scrape, mock_fetch, mock_repo_cls
    ):
        from app.models import Article

        mock_repo = MagicMock()
        mock_repo.get_by_url.return_value = None  # 新文章
        mock_repo.save.return_value = 1
        mock_repo_cls.return_value = mock_repo

        mock_fetch.return_value = [
            Article(title="新文章", article_url="https://new.com", author="公众号"),
        ], False

        mock_scrape.return_value = {
            "markdown_path": "/tmp/test.md",
            "content_hash": "abc123",
            "title": "新文章",
        }

        mock_path_instance = MagicMock()
        mock_path_instance.read_text.return_value = "文章内容"
        mock_path_cls.return_value = mock_path_instance

        mock_summarizer = MagicMock()
        mock_summarizer.summarize.return_value = "摘要"
        mock_summarizer_cls.return_value = mock_summarizer

        config = AppConfig()
        sync_job = create_sync_job(config)
        sync_job()

        mock_scrape.assert_called_once()
        mock_repo.save.assert_called_once()

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
    @patch("app.scheduler._send_cookie_alert")
    def test_sync_job_detects_cookie_expired(self, mock_alert, mock_fetch, mock_repo_cls):
        from app.models import Article

        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo

        mock_fetch.return_value = [], True  # cookie_expired=True

        config = AppConfig()
        sync_job = create_sync_job(config)
        sync_job()

        mock_alert.assert_called_once()
        mock_repo.save.assert_not_called()

    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.fetch_all_feeds")
    @patch("app.scheduler.scrape_article")
    @patch("app.scheduler.TruncateSummarizer")
    def test_sync_job_dead_letter(
        self, mock_summarizer_cls, mock_scrape, mock_fetch, mock_repo_cls
    ):
        from app.models import Article

        # 模拟已失败 5 次的文章
        existing_article = Article(
            id=2, title="失败文章", article_url="https://fail.com",
            author="公众号", status="failed", fail_count=5,
        )

        mock_repo = MagicMock()
        mock_repo.get_by_url.return_value = existing_article
        mock_repo_cls.return_value = mock_repo

        mock_fetch.return_value = [
            Article(title="失败文章", article_url="https://fail.com", author="公众号"),
        ], False

        mock_summarizer = MagicMock()
        mock_summarizer_cls.return_value = mock_summarizer

        config = AppConfig()
        sync_job = create_sync_job(config)
        sync_job()

        # 应标记为 permanent_failed，不调用 scrape
        mock_repo.update_status.assert_called_with(2, "permanent_failed")
        mock_scrape.assert_not_called()

    @patch("app.scheduler.ArticleRepository")
    @patch("app.scheduler.fetch_all_feeds")
    @patch("app.scheduler.scrape_article")
    @patch("app.scheduler.TruncateSummarizer")
    def test_sync_job_permanent_failed_skipped(
        self, mock_summarizer_cls, mock_scrape, mock_fetch, mock_repo_cls
    ):
        from app.models import Article

        existing_article = Article(
            id=3, title="永久失败", article_url="https://permfail.com",
            author="公众号", status="permanent_failed",
        )

        mock_repo = MagicMock()
        mock_repo.get_by_url.return_value = existing_article
        mock_repo_cls.return_value = mock_repo

        mock_fetch.return_value = [
            Article(title="永久失败", article_url="https://permfail.com", author="公众号"),
        ], False

        mock_summarizer = MagicMock()
        mock_summarizer_cls.return_value = mock_summarizer

        config = AppConfig()
        sync_job = create_sync_job(config)
        sync_job()

        mock_scrape.assert_not_called()
