# src/product_availability_domain/mysql_gtin_stock_repository
"""MySQL implementation of GTIN Stock repository."""

import logging
from datetime import datetime
from typing import Optional

import mysql.connector
from mysql.connector import Error

from src.common.config.settings import settings
from src.common.dtos.availability_dtos import (
    GtinStockItemDTO,
    GtinStockResponseDTO,
    SupplierContextDTO,
)
from src.common.exceptions.custom_exceptions import DatabaseError
from src.product_availability_domain.domain.repositories.gtin_stock_repository import (
    IGtinStockRepository,
)

logger = logging.getLogger(__name__)


class MySQLGtinStockRepository(IGtinStockRepository):
    """MySQL implementation of the GTIN Stock Repository."""

    def __init__(self) -> None:
        """Initializes the repository."""
        self._connection = None

    def _get_connection(self):
        """Establishes or returns an active MySQL database connection."""
        if not self._connection or not self._connection.is_connected():
            try:
                self._connection = mysql.connector.connect(
                    host=settings.DB_HOST,
                    database=settings.DB_DATABASE,
                    user=settings.DB_USER,
                    password=settings.DB_PASSWORD,
                    autocommit=False,  # Better control over transactions
                    charset="utf8mb4",
                    use_unicode=True,
                )
            except Error as e:
                raise DatabaseError(f"Failed to connect to MySQL: {e}", original_exception=e)
        return self._connection

    def create_tables(self) -> None:
        """Creates or updates tables for the GTIN Stock domain with 'pds_' prefix."""
        # Removed retailer_id and retailer_gln as they are constant business values
        create_gtin_stock_table_query = """
        CREATE TABLE IF NOT EXISTS pds_gtin_stock (
            id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
            supplier_id INT UNSIGNED NOT NULL,
            supplier_gln VARCHAR(255) NOT NULL,
            supplier_name VARCHAR(255),
            gtin VARCHAR(255) NOT NULL,
            quantity INT UNSIGNED,
            stock_traffic_light VARCHAR(50),
            item_type VARCHAR(50),
            timestamp DATETIME,
            date_synced DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_gtin_supplier (gtin, supplier_gln), -- Simplified unique constraint
            INDEX idx_supplier_gln (supplier_gln),
            INDEX idx_gtin (gtin),
            INDEX idx_gtin_supplier_composite (gtin, supplier_gln) -- Composite index for faster lookups
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(create_gtin_stock_table_query)
            conn.commit()
            logger.info("PDS GTIN Stock table checked/created.")
        except Error as e:
            conn.rollback()
            raise DatabaseError(f"Error creating PDS GTIN Stock table: {e}", original_exception=e)
        finally:
            cursor.close()

    def save_gtin_stock_item(self, supplier_context: SupplierContextDTO, item: GtinStockItemDTO) -> None:
        """Saves or updates a single GTIN stock item with its supplier context."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Removed retailer fields from the query
        insert_query = """
        INSERT INTO pds_gtin_stock 
        (supplier_id, supplier_gln, supplier_name, gtin, quantity, stock_traffic_light, item_type, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
        quantity = VALUES(quantity), 
        stock_traffic_light = VALUES(stock_traffic_light),
        item_type = VALUES(item_type),
        timestamp = VALUES(timestamp),
        date_synced = CURRENT_TIMESTAMP
        """
        params = (
            supplier_context.supplier_id,
            supplier_context.supplier_gln,
            supplier_context.supplier_name,
            item.gtin,
            item.quantity,
            item.stock_traffic_light,
            item.item_type,
            item.timestamp,
        )

        try:
            cursor.execute(insert_query, params)
            conn.commit()
        except Error as e:
            conn.rollback()
            raise DatabaseError(f"Error saving GTIN stock for {item.gtin}: {e}", original_exception=e)
        finally:
            cursor.close()

    def batch_save_gtin_stock_items(self, supplier_context: SupplierContextDTO, items: list[GtinStockItemDTO]) -> None:
        """
        Batch saves multiple GTIN stock items for better performance.
        Uses executemany for better performance with large datasets.
        """
        if not items:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO pds_gtin_stock 
        (supplier_id, supplier_gln, supplier_name, gtin, quantity, stock_traffic_light, item_type, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
        quantity = VALUES(quantity), 
        stock_traffic_light = VALUES(stock_traffic_light),
        item_type = VALUES(item_type),
        timestamp = VALUES(timestamp),
        date_synced = CURRENT_TIMESTAMP
        """

        params_list = [
            (
                supplier_context.supplier_id,
                supplier_context.supplier_gln,
                supplier_context.supplier_name,
                item.gtin,
                item.quantity,
                item.stock_traffic_light,
                item.item_type,
                item.timestamp,
            )
            for item in items
        ]

        try:
            cursor.executemany(insert_query, params_list)
            conn.commit()
            logger.info(f"Batch saved {len(items)} GTIN stock items for supplier {supplier_context.supplier_name}")
        except Error as e:
            conn.rollback()
            raise DatabaseError(f"Error batch saving GTIN stock items: {e}", original_exception=e)
        finally:
            cursor.close()

    def check_existing_gtin_supplier_pairs(self, gtin_supplier_pairs: list[tuple[str, str]]) -> set[tuple[str, str]]:
        """
        Checks which GTIN-Supplier pairs already exist in the database.
        Returns a set of existing pairs for quick lookup.
        """
        if not gtin_supplier_pairs:
            return set()

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Create placeholders for the IN clause
            placeholders = ",".join(["(%s, %s)"] * len(gtin_supplier_pairs))
            query = f"""
            SELECT gtin, supplier_gln 
            FROM pds_gtin_stock 
            WHERE (gtin, supplier_gln) IN ({placeholders})
            """

            # Flatten the list of tuples for the query parameters
            params = [item for pair in gtin_supplier_pairs for item in pair]

            cursor.execute(query, params)
            results = cursor.fetchall()

            return set((row[0], row[1]) for row in results)

        except Error as e:
            raise DatabaseError(f"Error checking existing GTIN-Supplier pairs: {e}", original_exception=e)
        finally:
            cursor.close()

    def get_gtin_stock_by_supplier_context(self, supplier_context: SupplierContextDTO) -> GtinStockResponseDTO:
        """Retrieves all GTIN stock for a given supplier context (retailer context removed from DB)."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)

        stock_items: list[GtinStockItemDTO] = []

        try:
            query = """
            SELECT gtin, quantity, stock_traffic_light, item_type, timestamp
            FROM pds_gtin_stock
            WHERE supplier_gln = %s
            """
            cursor.execute(query, (supplier_context.supplier_gln,))
            rows = cursor.fetchall()

            for row in rows:
                stock_items.append(
                    GtinStockItemDTO(
                        gtin=row["gtin"],
                        quantity=row["quantity"],
                        stock_traffic_light=row["stock_traffic_light"],
                        item_type=row["item_type"],
                        timestamp=row["timestamp"],
                    )
                )

            return GtinStockResponseDTO(supplier_context=supplier_context, stock_items=stock_items)

        except Error as e:
            raise DatabaseError(
                f"Error fetching GTIN stock by supplier GLN {supplier_context.supplier_gln}: {e}", original_exception=e
            )
        finally:
            cursor.close()

    def get_gtin_stock_by_gtin_and_supplier(self, gtin: str, supplier_gln: str) -> Optional[GtinStockItemDTO]:
        """Retrieves a specific GTIN stock item by GTIN and supplier GLN."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        item_dto = None
        try:
            query = """
            SELECT gtin, quantity, stock_traffic_light, item_type, timestamp
            FROM pds_gtin_stock
            WHERE gtin = %s AND supplier_gln = %s
            LIMIT 1
            """
            cursor.execute(query, (gtin, supplier_gln))
            row = cursor.fetchone()
            if row:
                item_dto = GtinStockItemDTO(
                    gtin=row["gtin"],
                    quantity=row["quantity"],
                    stock_traffic_light=row["stock_traffic_light"],
                    item_type=row["item_type"],
                    timestamp=row["timestamp"],
                )
        except Error as e:
            raise DatabaseError(
                f"Error fetching GTIN stock for GTIN {gtin}, Supplier GLN {supplier_gln}: {e}", original_exception=e
            )
        finally:
            cursor.close()
        return item_dto

    def get_all_gtin_codes(self) -> list[str]:
        """Retrieves all unique GTIN codes from pds_gtin_stock table."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT DISTINCT gtin FROM pds_gtin_stock WHERE gtin IS NOT NULL AND gtin != ''")
            results = cursor.fetchall()
            return [row[0] for row in results]
        except Error as e:
            raise DatabaseError(f"Error fetching GTIN codes: {e}", original_exception=e)
        finally:
            cursor.close()

    def get_unique_supplier_glns(self) -> list[str]:
        """Retrieves all unique supplier GLNs from pds_gtin_stock table."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT DISTINCT supplier_gln FROM pds_gtin_stock WHERE supplier_gln IS NOT NULL AND supplier_gln != ''"
            )
            results = cursor.fetchall()
            return [row[0] for row in results]
        except Error as e:
            raise DatabaseError(f"Error fetching supplier GLNs: {e}", original_exception=e)
        finally:
            cursor.close()

    def get_all_supplier_gtin_pairs(self) -> list[tuple[str, str]]:
        """Retrieves all unique supplier_gln and gtin pairs."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT DISTINCT supplier_gln, gtin FROM pds_gtin_stock WHERE supplier_gln IS NOT NULL AND supplier_gln != '' AND gtin IS NOT NULL AND gtin != ''"
            )
            results = cursor.fetchall()
            return [(row[0], row[1]) for row in results]
        except Error as e:
            raise DatabaseError(f"Error fetching all supplier GLN and GTIN pairs: {e}", original_exception=e)
        finally:
            cursor.close()

    def __del__(self) -> None:
        """Closes the database connection when the object is destroyed."""
        if self._connection and self._connection.is_connected():
            self._connection.close()
