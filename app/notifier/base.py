from abc import ABC, abstractmethod

from app.models import Article


class BaseNotifier(ABC):
    @abstractmethod
    def send(self, articles: list[Article], summaries: list[str]) -> bool:
        ...
