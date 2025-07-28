"""MySQL implementation of GTIN Stock repository."""

import mysql.connector
from mysql.connector import Error
import logging
from datetime import datetime
from src.common.config.settings import settings
from src.common.exceptions.custom_exceptions import DatabaseError
from src.common.dtos.availability_dtos import SupplierContextDTO, GtinStockItemDTO, GtinStockResponseDTO
from src.product_availability_domain.domain.repositories.gtin_stock_repository import IGtinStockRepository

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
                )
            except Error as e:
                raise DatabaseError(f"Failed to connect to MySQL: {e}", original_exception=e)
        return self._connection

    def create_tables(self) -> None:
        """Creates or updates tables for the GTIN Stock domain with 'pds_' prefix."""
        create_gtin_stock_table_query = """
        CREATE TABLE IF NOT EXISTS pds_gtin_stock (
            id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
            retailer_id VARCHAR(255) NOT NULL,
            retailer_gln VARCHAR(255) NOT NULL,
            supplier_id INT UNSIGNED NOT NULL,
            supplier_gln VARCHAR(255) NOT NULL,
            supplier_name VARCHAR(255),
            gtin VARCHAR(255) NOT NULL,
            quantity INT UNSIGNED,
            stock_traffic_light VARCHAR(50),
            item_type VARCHAR(50),
            timestamp DATETIME,
            date_synced DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_gtin_supplier_retailer (gtin, supplier_gln, retailer_gln), -- Unique per GTIN, supplier, and retailer context
            INDEX idx_supplier_gln (supplier_gln),
            INDEX idx_retailer_gln (retailer_gln),
            INDEX idx_gtin (gtin)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(create_gtin_stock_table_query)
            conn.commit()
            print("PDS GTIN Stock table checked/created.")
        except Error as e:
            conn.rollback()
            raise DatabaseError(f"Error creating PDS GTIN Stock table: {e}", original_exception=e)
        finally:
            cursor.close()

    def save_gtin_stock_item(self, supplier_context: SupplierContextDTO, item: GtinStockItemDTO) -> None:
        """Saves or updates a single GTIN stock item with its supplier context."""
        conn = self._get_connection()
        cursor = conn.cursor()

        insert_query = """
        INSERT INTO pds_gtin_stock 
        (retailer_id, retailer_gln, supplier_id, supplier_gln, supplier_name, gtin, quantity, stock_traffic_light, item_type, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
        quantity = VALUES(quantity), 
        stock_traffic_light = VALUES(stock_traffic_light),
        item_type = VALUES(item_type),
        timestamp = VALUES(timestamp),
        date_synced = CURRENT_TIMESTAMP
        """
        params = (
            supplier_context.retailer_id,
            supplier_context.retailer_gln,
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

    def get_gtin_stock_by_supplier_context(self, supplier_context: SupplierContextDTO) -> GtinStockResponseDTO:
        """Retrieves all GTIN stock for a given supplier and retailer context."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)

        stock_items: list[GtinStockItemDTO] = []

        try:
            query = """
            SELECT gtin, quantity, stock_traffic_light, item_type, timestamp
            FROM pds_gtin_stock
            WHERE supplier_gln = %s AND retailer_gln = %s
            """
            cursor.execute(query, (supplier_context.supplier_gln, supplier_context.retailer_gln))
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

    def get_gtin_stock_by_gtin_and_supplier(self, gtin: str, supplier_gln: str) -> GtinStockItemDTO | None:
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
