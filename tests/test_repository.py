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
