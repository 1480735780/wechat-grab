from abc import ABC, abstractmethod


class BaseSummarizer(ABC):
    @abstractmethod
    def summarize(self, markdown_content: str) -> str:
        ...


class TruncateSummarizer(BaseSummarizer):
    """第一版：截取前 N 个字符"""

    def __init__(self, max_length: int = 200):
        self.max_length = max_length

    def summarize(self, markdown_content: str) -> str:
        if not markdown_content:
            return ""
        # 去掉 frontmatter
        if markdown_content.startswith("---"):
            end = markdown_content.find("---", 3)
            if end != -1:
                markdown_content = markdown_content[end + 3:].strip()
        return markdown_content[: self.max_length]
