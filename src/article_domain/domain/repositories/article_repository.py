# article_domain/domain/repositories/article_repository.py
"""Article repository interface."""
from abc import ABC, abstractmethod

from src.common.dtos.article_dtos import ArticleDataDTO


class IArticleRepository(ABC):
    @abstractmethod
    def save_article(self, article_data: ArticleDataDTO) -> None:
        """Saves or updates article data in the persistence layer."""
        pass

    @abstractmethod
    def get_article_by_ecc_id(self, ecc_id: int) -> ArticleDataDTO:
        """Retrieves an article by its ECC ID."""
        pass

    @abstractmethod
    def get_all_articles(self) -> list[ArticleDataDTO]:
        """Retrieves all articles."""
        pass
