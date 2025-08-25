# ruff: noqa: E501
# article_domain/infrastructure/persistence/mysql_article_repository.py
"""MySQL implementation of Article repository."""
import logging

import mysql.connector
from mysql.connector import Error

from src.article_domain.domain.repositories.article_repository import IArticleRepository
from src.common.config.settings import settings
from src.common.dtos.article_dtos import ArticleDataDTO, AttributeDTO, ImageDTO
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
            INDEX (productFamilyEccId)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        create_attributes_table_query = """
        CREATE TABLE IF NOT EXISTS pds_article_attributes (
            id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
            article_eccId INT UNSIGNED NOT NULL,
            attribute_key VARCHAR(255) NOT NULL,
            attribute_value TEXT,
            attribute_unit VARCHAR(50),
            FOREIGN KEY (article_eccId) REFERENCES pds_articles(eccId) ON DELETE CASCADE,
            INDEX (article_eccId),
            INDEX (attribute_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        create_images_table_query = """
        CREATE TABLE IF NOT EXISTS pds_article_images (
            id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
            article_eccId INT UNSIGNED NOT NULL,
            image_url VARCHAR(1024) NOT NULL,
            image_type VARCHAR(50),
            sort_index SMALLINT UNSIGNED,
            FOREIGN KEY (article_eccId) REFERENCES pds_articles(eccId) ON DELETE CASCADE,
            INDEX (article_eccId),
            INDEX (image_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor = self._get_connection().cursor()
        try:
            cursor.execute(create_articles_table_query)
            cursor.execute(create_attributes_table_query)
            cursor.execute(create_images_table_query)
            self._get_connection().commit()
            logger.info("PDS Article tables checked/created.")
        except Error as e:
            self._get_connection().rollback()
            raise DatabaseError(f"Error creating PDS Article tables: {e}", original_exception=e)
        finally:
            cursor.close()

    def save_article(self, article_dto: ArticleDataDTO) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()

        article_main_data = article_dto.__dict__.copy()
        for key in ["attributes", "images"]:
            if key in article_main_data:
                del article_main_data[key]

        article_main_data["dateChanged"] = format_datetime_for_db(article_main_data.get("dateChanged"))
        article_main_data["seasonDateFrom"] = format_date_for_db(article_main_data.get("seasonDateFrom"))
        article_main_data["seasonDateTo"] = format_date_for_db(article_main_data.get("seasonDateTo"))

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

            cursor.execute("DELETE FROM pds_article_attributes WHERE article_eccId = %s", (article_dto.eccId,))
            cursor.execute("DELETE FROM pds_article_images WHERE article_eccId = %s", (article_dto.eccId,))

            if article_dto.attributes:
                attr_values = [(article_dto.eccId, attr.key, attr.value, attr.unit) for attr in article_dto.attributes]
                cursor.executemany(
                    """
                    INSERT INTO pds_article_attributes (article_eccId, attribute_key, attribute_value, attribute_unit)
                    VALUES (%s, %s, %s, %s)
                """,
                    attr_values,
                )

            if article_dto.images:
                img_values = [(article_dto.eccId, img.url, img.type, img.sortIndex) for img in article_dto.images]
                cursor.executemany(
                    """
                    INSERT INTO pds_article_images (article_eccId, image_url, image_type, sort_index)
                    VALUES (%s, %s, %s, %s)
                """,
                    img_values,
                )

            conn.commit()
        except Error as e:
            conn.rollback()
            raise DatabaseError(f"Error saving article {article_dto.eccId}: {e}", original_exception=e)
        finally:
            cursor.close()

    def get_all_articles(self) -> list[ArticleDataDTO]:
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        all_articles_dtos = []

        try:
            cursor.execute("SELECT * FROM pds_articles")
            articles_raw = cursor.fetchall()

            for art_raw in articles_raw:
                cursor.execute(
                    "SELECT attribute_key as key, attribute_value as value, attribute_unit as unit FROM pds_article_attributes WHERE article_eccId = %s",
                    (art_raw["eccId"],),
                )
                attributes_raw = cursor.fetchall()
                attributes_dtos = [AttributeDTO(**a) for a in attributes_raw]

                cursor.execute(
                    "SELECT image_url as url, image_type as type, sort_index as sortIndex FROM pds_article_images WHERE article_eccId = %s",
                    (art_raw["eccId"],),
                )
                images_raw = cursor.fetchall()
                images_dtos = [ImageDTO(**i) for i in images_raw]

                article_dto_data = {k: v for k, v in art_raw.items() if k not in ["attributes", "images"]}
                all_articles_dtos.append(
                    ArticleDataDTO(**article_dto_data, attributes=attributes_dtos, images=images_dtos)
                )
        except Error as e:
            raise DatabaseError(f"Error fetching all articles: {e}", original_exception=e)
        finally:
            cursor.close()
        return all_articles_dtos

    def get_article_by_ecc_id(self, ecc_id: int) -> ArticleDataDTO | None:
        """Retrieves a single article by its ECC ID."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        article_dto = None
        try:
            cursor.execute("SELECT * FROM pds_articles WHERE eccId = %s", (ecc_id,))
            art_raw = cursor.fetchone()

            if art_raw:
                cursor.execute(
                    "SELECT attribute_key as key, attribute_value as value, attribute_unit as unit FROM pds_article_attributes WHERE article_eccId = %s",
                    (art_raw["eccId"],),
                )
                attributes_raw = cursor.fetchall()
                attributes_dtos = [AttributeDTO(**a) for a in attributes_raw]

                cursor.execute(
                    "SELECT image_url as url, image_type as type, sort_index as sortIndex FROM pds_article_images WHERE article_eccId = %s",
                    (art_raw["eccId"],),
                )
                images_raw = cursor.fetchall()
                images_dtos = [ImageDTO(**i) for i in images_raw]

                article_dto_data = {k: v for k, v in art_raw.items() if k not in ["attributes", "images"]}
                article_dto = ArticleDataDTO(**article_dto_data, attributes=attributes_dtos, images=images_dtos)
        except Error as e:
            raise DatabaseError(f"Error fetching article by eccId {ecc_id}: {e}", original_exception=e)
        finally:
            cursor.close()
        return article_dto

    def __del__(self) -> None:
        if self._connection and self._connection.is_connected():
            self._connection.close()
