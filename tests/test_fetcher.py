from unittest.mock import MagicMock, patch

from app.fetcher import fetch_feed, fetch_all_feeds
from app.models import Subscription


class TestFetcher:
    @patch("app.fetcher.feedparser.parse")
    @patch("app.fetcher.requests.get")
    def test_fetch_feed_success(self, mock_requests_get, mock_parse):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<rss></rss>"
        mock_response.encoding = "utf-8"
        mock_requests_get.return_value = mock_response

        mock_entry = MagicMock()
        mock_entry.title = "测试文章"
        mock_entry.link = "https://mp.weixin.qq.com/s/test123"
        mock_entry.published = "Sun, 08 Jun 2026 10:30:00 +0800"
        mock_entry.published_parsed = (2026, 6, 8, 10, 30, 0, 0, 0, 0)
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
    @patch("app.fetcher.requests.get")
    def test_fetch_feed_empty(self, mock_requests_get, mock_parse):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<rss></rss>"
        mock_response.encoding = "utf-8"
        mock_requests_get.return_value = mock_response

        mock_feed = MagicMock()
        mock_feed.entries = []
        mock_feed.bozo = 0
        mock_parse.return_value = mock_feed

        sub = Subscription(name="空公众号", rss_path="/wechat/mp/empty")
        articles = fetch_feed(sub, base_url="https://rsshub.app")
        assert len(articles) == 0

    @patch("app.fetcher.requests.get")
    def test_fetch_feed_failure_returns_empty(self, mock_requests_get):
        mock_requests_get.side_effect = Exception("Connection error")

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
        articles, cookie_expired = fetch_all_feeds(subs, base_url="https://rsshub.app")
        assert len(articles) == 2
        assert cookie_expired is False
