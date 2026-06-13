from unittest.mock import MagicMock, patch

from app.fetcher import fetch_feed, fetch_mp_articles, fetch_all_feeds
from app.models import Subscription


class TestFetcher:
    @patch("app.fetcher.feedparser.parse")
    @patch("app.fetcher.requests.Session")
    def test_fetch_feed_success(self, mock_session_cls, mock_parse):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<rss></rss>"
        mock_response.encoding = "utf-8"
        mock_session.get.return_value = mock_response

        mock_entry = MagicMock()
        mock_entry.title = "测试文章"
        mock_entry.link = "https://mp.weixin.qq.com/s/test123"
        mock_entry.published = "Sun, 08 Jun 2026 10:30:00 +0800"
        mock_entry.published_parsed = (2026, 6, 8, 10, 30, 0, 0, 0, 0)
        mock_entry.author = "测试公众号"
        del mock_entry.updated_parsed

        mock_feed = MagicMock()
        mock_feed.entries = [mock_entry]
        mock_feed.bozo = 0
        mock_parse.return_value = mock_feed

        sub = Subscription(name="测试公众号", rss_path="/wechat/mp/test")
        articles = fetch_feed(sub, base_url="http://localhost:1200")

        assert len(articles) == 1
        assert articles[0].title == "测试文章"
        assert articles[0].article_url == "https://mp.weixin.qq.com/s/test123"
        assert articles[0].author == "测试公众号"

    @patch("app.fetcher.feedparser.parse")
    @patch("app.fetcher.requests.Session")
    def test_fetch_feed_empty(self, mock_session_cls, mock_parse):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<rss></rss>"
        mock_response.encoding = "utf-8"
        mock_session.get.return_value = mock_response

        mock_feed = MagicMock()
        mock_feed.entries = []
        mock_feed.bozo = 0
        mock_parse.return_value = mock_feed

        sub = Subscription(name="空公众号", rss_path="/wechat/mp/empty")
        articles = fetch_feed(sub, base_url="http://localhost:1200")
        assert len(articles) == 0

    @patch("app.fetcher.requests.Session")
    def test_fetch_feed_failure_returns_empty(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = Exception("Connection error")

        sub = Subscription(name="失败公众号", rss_path="/wechat/mp/fail")
        articles = fetch_feed(sub, base_url="http://localhost:1200")
        assert len(articles) == 0

    @patch("app.fetcher.fetch_feed")
    def test_fetch_all_feeds_rsshub(self, mock_fetch_feed):
        from app.models import Article

        mock_fetch_feed.return_value = [
            Article(title="文章1", article_url="https://mp.weixin.qq.com/s/1", author="公众号A"),
        ]

        subs = [
            Subscription(name="公众号A", rss_path="/wechat/mp/a"),
            Subscription(name="公众号B", rss_path="/wechat/mp/b"),
        ]
        result = fetch_all_feeds(subs, base_url="http://localhost:1200")
        assert len(result.articles) == 2
        assert len(result.alerts) == 0


class TestMPFetcher:
    @patch("app.fetcher.requests.Session")
    def test_fetch_mp_articles_success(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ret": 0,
            "app_msg_list": [
                {"title": "MP文章1", "link": "https://mp.weixin.qq.com/s/mp1", "update_time": 1717836000},
                {"title": "MP文章2", "link": "https://mp.weixin.qq.com/s/mp2", "update_time": 1717832400},
            ],
        }
        mock_session.get.return_value = mock_response

        sub = Subscription(name="测试公众号", rss_path="/wechat/mp/test_biz_id")
        articles, alert = fetch_mp_articles(sub, cookie="test_cookie", token="test_token")

        assert len(articles) == 2
        assert articles[0].title == "MP文章1"
        assert alert is None

    @patch("app.fetcher.requests.Session")
    def test_fetch_mp_articles_cookie_expired(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ret": 200013, "msg": "invalid csrf token"}
        mock_session.get.return_value = mock_response

        sub = Subscription(name="测试公众号", rss_path="/wechat/mp/test_biz")
        articles, alert = fetch_mp_articles(sub, cookie="expired_cookie", token="expired_token")

        assert len(articles) == 0
        assert alert is not None
        assert alert.key == "COOKIE_EXPIRED"
        assert alert.error_code == 200013

    @patch("app.fetcher.requests.Session")
    def test_fetch_mp_articles_no_articles(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ret": 0, "app_msg_list": []}
        mock_session.get.return_value = mock_response

        sub = Subscription(name="空公众号", rss_path="/wechat/mp/empty_biz")
        articles, alert = fetch_mp_articles(sub, cookie="test_cookie", token="test_token")

        assert len(articles) == 0
        assert alert is None

    @patch("app.fetcher.requests.Session")
    def test_fetch_mp_articles_network_error(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = Exception("Connection error")

        sub = Subscription(name="失败公众号", rss_path="/wechat/mp/fail_biz")
        articles, alert = fetch_mp_articles(sub, cookie="test_cookie", token="test_token")

        assert len(articles) == 0
        assert alert is None

    @patch("app.fetcher.fetch_mp_articles")
    @patch("app.fetcher.fetch_feed")
    def test_fetch_all_feeds_mp_priority(self, mock_rsshub, mock_mp):
        from app.models import Article

        mock_mp.return_value = (
            [Article(title="MP文章", article_url="https://mp.weixin.qq.com/s/mp1", author="公众号A")],
            None,
        )
        mock_rsshub.return_value = []

        subs = [Subscription(name="公众号A", rss_path="/wechat/mp/a")]
        result = fetch_all_feeds(subs, mp_cookie="cookie", mp_token="token")

        assert len(result.articles) == 1
        assert result.articles[0].title == "MP文章"
        mock_mp.assert_called_once()
        mock_rsshub.assert_not_called()

    @patch("app.fetcher.fetch_mp_articles")
    @patch("app.fetcher.fetch_feed")
    def test_fetch_all_feeds_fallback_to_rsshub(self, mock_rsshub, mock_mp):
        from app.models import Article

        mock_mp.return_value = ([], None)  # MP 返回空
        mock_rsshub.return_value = [
            Article(title="RSS文章", article_url="https://mp.weixin.qq.com/s/rss1", author="公众号A"),
        ]

        subs = [Subscription(name="公众号A", rss_path="/wechat/mp/a")]
        result = fetch_all_feeds(subs, mp_cookie="cookie", mp_token="token")

        assert len(result.articles) == 1
        assert result.articles[0].title == "RSS文章"
        mock_mp.assert_called_once()
        mock_rsshub.assert_called_once()

    @patch("app.fetcher.fetch_mp_articles")
    @patch("app.fetcher.fetch_feed")
    def test_fetch_all_feeds_no_mp_config(self, mock_rsshub, mock_mp):
        from app.models import Article

        mock_rsshub.return_value = [
            Article(title="RSS文章", article_url="https://mp.weixin.qq.com/s/rss1", author="公众号A"),
        ]

        subs = [Subscription(name="公众号A", rss_path="/wechat/mp/a")]
        result = fetch_all_feeds(subs, mp_cookie="", mp_token="")

        assert len(result.articles) == 1
        mock_mp.assert_not_called()
        mock_rsshub.assert_called_once()

    @patch("app.fetcher.fetch_mp_articles")
    @patch("app.fetcher.fetch_feed")
    def test_fetch_all_feeds_collects_cookie_alert(self, mock_rsshub, mock_mp):
        from app.models import Alert, Article

        # MP API Cookie 过期
        alert = Alert(key="COOKIE_EXPIRED", title="Cookie过期", message="error", error_code=200013)
        mock_mp.return_value = ([], alert)
        # RSSHub 降级成功
        mock_rsshub.return_value = [
            Article(title="RSS文章", article_url="https://mp.weixin.qq.com/s/rss1", author="公众号A"),
        ]

        subs = [Subscription(name="公众号A", rss_path="/wechat/mp/a")]
        result = fetch_all_feeds(subs, mp_cookie="cookie", mp_token="token")

        # 只有 COOKIE_EXPIRED 告警，没有 RSSHUB_UNREACHABLE
        assert len(result.alerts) == 1
        assert result.alerts[0].key == "COOKIE_EXPIRED"

    @patch("app.fetcher.fetch_feed")
    def test_fetch_all_feeds_rsshub_down_alert(self, mock_rsshub):
        """RSSHub 所有源返回空时，应生成 RSSHUB_UNREACHABLE 告警"""
        mock_rsshub.return_value = []

        subs = [Subscription(name="公众号A", rss_path="/wechat/mp/a")]
        result = fetch_all_feeds(subs, mp_cookie="", mp_token="")

        assert len(result.articles) == 0
        assert len(result.alerts) == 1
        assert result.alerts[0].key == "RSSHUB_UNREACHABLE"
