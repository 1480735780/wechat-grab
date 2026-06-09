from app.summarizer import TruncateSummarizer


class TestTruncateSummarizer:
    def test_short_content(self):
        summarizer = TruncateSummarizer(max_length=200)
        result = summarizer.summarize("短内容")
        assert result == "短内容"

    def test_long_content(self):
        summarizer = TruncateSummarizer(max_length=200)
        content = "这是一段很长的内容。" * 100
        result = summarizer.summarize(content)
        assert len(result) <= 200

    def test_empty_content(self):
        summarizer = TruncateSummarizer(max_length=200)
        result = summarizer.summarize("")
        assert result == ""
