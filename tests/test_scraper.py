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
    @patch("app.scraper.requests.Session")
    def test_scrape_article_success(self, mock_session_cls):
        html_content = """
        <html><body>
        <div id="js_content">
            <h1>测试文章标题</h1>
            <p>这是文章正文内容。</p>
            <img src="https://mmbiz.qpic.cn/test.jpg" alt="测试图片">
        </div>
        </body></html>
        """
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        mock_response.encoding = "utf-8"
        mock_session.get.return_value = mock_response

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

    @patch("app.scraper.requests.Session")
    def test_scrape_article_failure(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.get.side_effect = Exception("Connection error")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = scrape_article(
                article_url="https://mp.weixin.qq.com/s/fail",
                author="测试公众号",
                output_base_dir=tmpdir,
            )
            assert result is None
