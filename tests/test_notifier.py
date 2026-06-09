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
