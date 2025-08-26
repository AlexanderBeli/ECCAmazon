# ruff: noqa: E501
# article_domain/infrastructure/persistence/mysql_article_repository.py
"""MySQL implementation of Article repository."""
import json
import logging

import mysql.connector
from mysql.connector import Error

from src.article_domain.domain.repositories.article_repository import IArticleRepository
from src.common.config.settings import settings
from src.common.dtos.article_dtos import ArticleDataDTO
from src.common.exceptions.custom_exceptions import DatabaseError
from src.common.utils.date_utils import format_date_for_db, format_datetime_for_db

logger = logging.getLogger(__name__)


class MySQLArticleRepository(IArticleRepository):
    def __init__(self) -> None:
        self._connection = None

    def _get_connection(self):
        if not self._connection or not self._connection.is_connected():
            try:
                self._connection = mysql.connector.connect(
                    host=settings.DB_HOST,
                    database=settings.DB_DATABASE,
                    user=settings.DB_USER,
                    password=settings.DB_PASSWORD,
                )
            except Error as e:
                raise DatabaseError(f"Failed to connect to MySQL: {e}", original_exception=e)
        return self._connection

    def create_tables(self) -> None:
        """Creates or updates tables for the Article domain with 'pds_' prefix."""
        create_articles_table_query = """
        CREATE TABLE IF NOT EXISTS pds_articles (
            eccId INT UNSIGNED PRIMARY KEY,
            ean VARCHAR(255),
            mainArticleEccId INT UNSIGNED,
            suGln VARCHAR(255),
            mfGln VARCHAR(255),
            suArticleNumber VARCHAR(255),
            mfArticleNumber VARCHAR(255),
            brandOriginal VARCHAR(255),
            brandCleared VARCHAR(255),
            modelName VARCHAR(255),
            articleName VARCHAR(500),
            catalogId INT UNSIGNED,
            catalogName VARCHAR(255),
            dateChanged DATETIME,
            status TINYINT UNSIGNED,
            textShort TEXT,
            textLong LONGTEXT,
            textHtml LONGTEXT,
            seasonEccId INT UNSIGNED,
            seasonName VARCHAR(255),
            seasonDateFrom DATE,
            seasonDateTo DATE,
            gender VARCHAR(50),
            ageGroup VARCHAR(50),
            productCategoryEccId INT UNSIGNED,
            productCategoryName VARCHAR(255),
            productGroupEccId INT UNSIGNED,
            productGroupName VARCHAR(255),
            productSubGroupEccId INT UNSIGNED,
            productSubGroupName VARCHAR(255),
            productFamilyEccId INT UNSIGNED,
            productFamilyName VARCHAR(255),
            pricePricat DECIMAL(10, 2),
            priceRetail DECIMAL(10, 2),
            priceBase DECIMAL(10, 2),
            taxClass VARCHAR(50),
            currency VARCHAR(10),
            countryIso VARCHAR(10),
            originCountry VARCHAR(255),
            colorCode VARCHAR(50),
            colorName VARCHAR(255),
            easColor VARCHAR(100),
            customsTariffNumber VARCHAR(50),
            tax INT UNSIGNED,
            shoeWidth VARCHAR(10),
            innerMaterial VARCHAR(255),
            orgColor VARCHAR(50),
            images JSON,
            INDEX (ean),
            INDEX (mainArticleEccId),
            INDEX (suGln),
            INDEX (mfGln),
            INDEX (brandOriginal),
            INDEX (brandCleared),
            INDEX (catalogId),
            INDEX (dateChanged),
            INDEX (seasonEccId),
            INDEX (gender),
            INDEX (ageGroup),
            INDEX (productCategoryEccId),
            INDEX (productGroupEccId),
            INDEX (productSubGroupEccId),
            INDEX (productFamilyEccId),
            INDEX (colorCode),
            INDEX (colorName)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        cursor = self._get_connection().cursor()
        try:
            cursor.execute(create_articles_table_query)
            self._get_connection().commit()
            logger.info("PDS Article table checked/created.")
        except Error as e:
            self._get_connection().rollback()
            raise DatabaseError(f"Error creating PDS Article table: {e}", original_exception=e)
        finally:
            cursor.close()

    def save_article(self, article_dto: ArticleDataDTO) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()

        article_main_data = article_dto.__dict__.copy()

        article_main_data["dateChanged"] = format_datetime_for_db(article_main_data.get("dateChanged"))
        article_main_data["seasonDateFrom"] = format_date_for_db(article_main_data.get("seasonDateFrom"))
        article_main_data["seasonDateTo"] = format_date_for_db(article_main_data.get("seasonDateTo"))

        if "images" in article_main_data and article_main_data["images"]:
            article_main_data["images"] = json.dumps(article_main_data["images"])
        else:
            article_main_data["images"] = json.dumps([])

        columns = ", ".join(article_main_data.keys())
        placeholders = ", ".join(["%s"] * len(article_main_data))
        update_set = ", ".join([f"{col} = %s" for col in article_main_data])

        insert_query = (
            f"INSERT INTO pds_articles ({columns}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_set}"
        )
        values = list(article_main_data.values())
        params = values + values

        try:
            cursor.execute(insert_query, params)
            conn.commit()
            logger.info(f"Article {article_dto.eccId} saved successfully.")
        except Error as e:
            conn.rollback()
            raise DatabaseError(f"Error saving article {article_dto.eccId}: {e}", original_exception=e)
        finally:
            cursor.close()

    def get_all_articles(self, limit: int = None, offset: int = 0) -> list[ArticleDataDTO]:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM pds_articles"
        params = []

        if limit is not None:
            query += " LIMIT %s OFFSET %s"
            params = [limit, offset]

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()

            articles = []
            for row in rows:
                if row.get("images"):
                    try:
                        row["images"] = json.loads(row["images"])
                    except (json.JSONDecodeError, TypeError):
                        row["images"] = []
                else:
                    row["images"] = []

                articles.append(ArticleDataDTO(**row))

            return articles

        except Error as e:
            raise DatabaseError(f"Error fetching articles: {e}", original_exception=e)
        finally:
            cursor.close()

    def get_article_by_ecc_id(self, ecc_id: int) -> ArticleDataDTO | None:
        """Retrieves a single article by its ECC ID."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        article_dto = None
        try:
            cursor.execute("SELECT * FROM pds_articles WHERE eccId = %s", (ecc_id,))
            row = cursor.fetchone()

            if row.get("images"):
                try:
                    row["images"] = json.loads(row["images"])
                except (json.JSONDecodeError, TypeError):
                    row["images"] = []
            else:
                row["images"] = []

            article_dto = ArticleDataDTO(**row)
        except Error as e:
            raise DatabaseError(f"Error fetching article by eccId {ecc_id}: {e}", original_exception=e)
        finally:
            cursor.close()
        return article_dto

    def __del__(self) -> None:
        if self._connection and self._connection.is_connected():
            self._connection.close()

    def delete_article(self, ecc_id: int) -> None:
        """Delete article by eccId."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM pds_articles WHERE eccId = %s", (ecc_id,))
            conn.commit()

            if cursor.rowcount == 0:
                logger.warning(f"Article with eccId {ecc_id} not found for deletion")
            else:
                logger.info(f"Article {ecc_id} deleted successfully.")

        except Error as e:
            conn.rollback()
            raise DatabaseError(f"Error deleting article {ecc_id}: {e}", original_exception=e)
        finally:
            cursor.close()

    def search_articles(self, **filters) -> list[ArticleDataDTO]:
        """Search articles by different filtres."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)

        where_conditions = []
        params = []

        for field, value in filters.items():
            if value is not None:
                where_conditions.append(f"{field} = %s")
                params.append(value)

        query = "SELECT * FROM pds_articles"
        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()

            articles = []
            for row in rows:
                if row.get("images"):
                    try:
                        row["images"] = json.loads(row["images"])
                    except (json.JSONDecodeError, TypeError):
                        row["images"] = []
                else:
                    row["images"] = []

                articles.append(ArticleDataDTO(**row))

            return articles

        except Error as e:
            raise DatabaseError(f"Error searching articles: {e}", original_exception=e)
        finally:
            cursor.close()
