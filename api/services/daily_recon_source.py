"""
Daily Reconciliation Source Connector
======================================

Executes the stored extraction query against the external SQL Server
(which hosts the FIGARO_CL linked server) via pyodbc, mapping each result
row to a dict keyed by the canonical column names.

pyodbc is used synchronously because extraction runs inside a synchronous
Celery worker task.
"""

import logging

from api.daily_recon.columns import COLUMN_NAMES
from api.daily_recon.source_query import (
    DAILY_RECON_QUERY,
    get_source_odbc_connection_string,
)

logger = logging.getLogger(__name__)


def extract_rows(query: str | None = None) -> list[dict[str, object]]:
    """Run the extraction query and return rows as dicts keyed by column name.

    Args:
        query: Optional SQL override. Defaults to the stored
            ``DAILY_RECON_QUERY``.

    Returns:
        A list of row dicts. Keys are canonical column names from
        ``COLUMN_NAMES``; values are the raw values returned by the driver.

    Raises:
        RuntimeError: If the ODBC connection string is missing.
        ImportError: If pyodbc is not installed.
    """
    import pyodbc  # Imported lazily so the API/tests run without the driver.

    sql = query or DAILY_RECON_QUERY
    conn_str = get_source_odbc_connection_string()

    logger.info("Connecting to SQL Server source for daily reconciliation.")
    rows: list[dict[str, object]] = []

    with pyodbc.connect(conn_str, autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)

            # Map driver column order to canonical names. The outer SELECT *
            # surfaces the inner aliases, so prefer matching by name (upper).
            driver_columns = [col[0] for col in cursor.description]
            upper_to_canonical = {c.upper(): c for c in COLUMN_NAMES}

            for record in cursor.fetchall():
                row: dict[str, object] = {}
                for idx, driver_col in enumerate(driver_columns):
                    canonical = upper_to_canonical.get(
                        driver_col.upper(),
                        # Fall back to positional mapping if name is unknown.
                        COLUMN_NAMES[idx] if idx < len(COLUMN_NAMES) else driver_col,
                    )
                    row[canonical] = record[idx]
                rows.append(row)

    logger.info("Extracted %d rows from SQL Server source.", len(rows))
    return rows

