#!/usr/bin/env python3
"""
DTF Runner
==========

Generates System i Data Transfer (.dtf) configuration files for
period-based SQL extraction. Supports future execution via Power Automate.

Version 1.0 Changes:
- Initial implementation for Phase 4 period-based extraction
"""
from __future__ import annotations

import logging
import time
from pathlib import Path


class DTFRunner:
    """Generates and (in future) executes DTF files for System i Data Transfer.

    The DTF format is an INI-style configuration file used by IBM System i
    Data Transfer to run an SQL query against the AS/400 and write results
    to a local CSV file.

    The template at ``TEMPLATE_PATH`` contains two placeholder tokens:

    - ``{SQL_QUERY}`` — replaced with the SQL SELECT statement
    - ``{OUTPUT_PATH}`` — replaced with the local CSV output path

    Example:
        >>> runner = DTFRunner()
        >>> dtf = runner.generate_dtf_from_template(
        ...     "BuyerID_period.sql",
        ...     {"START_DATE": "2025-07-01", "END_DATE": "2025-09-30"},
        ...     "data/extracts/buyer_id_FY26_Q2.csv",
        ...     "data/extracts/buyer_id_FY26_Q2.dtf",
        ... )
    """

    TEMPLATE_PATH = (
        Path(__file__).parent.parent / "sql_templates" / "AS400_DataTransfer_template.dtf"
    )

    def generate_dtf(
        self,
        sql_query: str,
        output_csv_path: str | Path,
        dtf_output_path: str | Path,
        template_path: str | Path | None = None,
    ) -> Path:
        """Generate a DTF file with the SQL query and output path injected.

        Args:
            sql_query: The SQL SELECT statement to inject into the DTF.
            output_csv_path: Where System i Data Transfer should write the CSV.
            dtf_output_path: Where to save the generated .dtf file.
            template_path: Override the default template path.

        Returns:
            Path to the generated DTF file.
        """
        template = Path(template_path or self.TEMPLATE_PATH)
        content = template.read_text(encoding="utf-8")
        content = content.replace("{OUTPUT_PATH}", str(output_csv_path))
        content = content.replace("{SQL_QUERY}", sql_query)
        output = Path(dtf_output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        return output

    def generate_dtf_from_template(
        self,
        sql_template_path: str | Path,
        parameters: dict[str, str],
        output_csv_path: str | Path,
        dtf_output_path: str | Path,
    ) -> Path:
        """Generate a DTF from a SQL template file with parameter substitution.

        Reads the SQL template, substitutes all ``{PARAM}`` placeholders with
        the provided values, then delegates to :meth:`generate_dtf`.

        Args:
            sql_template_path: Path to .sql file with ``{PARAM}`` placeholders.
            parameters: Mapping of ``PARAM`` names to substitution values.
            output_csv_path: CSV output path for System i Data Transfer.
            dtf_output_path: Path to write the .dtf file.

        Returns:
            Path to the generated DTF file.
        """
        sql = Path(sql_template_path).read_text(encoding="utf-8")
        for key, value in parameters.items():
            sql = sql.replace(f"{{{key}}}", value)
        return self.generate_dtf(sql, output_csv_path, dtf_output_path)

    def execute_dtf(self, dtf_path: str | Path) -> bool:
        """Execute a DTF file using System i Data Transfer (future integration point).

        Note:
            This method is a stub for future Power Automate / System i
            integration.  Currently logs the intent and returns ``False``.

        Args:
            dtf_path: Path to the .dtf configuration file.

        Returns:
            True if execution succeeded, False otherwise.
        """
        logging.getLogger(__name__).warning(
            "DTF execution not yet implemented — file generated at %s. "
            "Execute manually via System i Data Transfer or via Power Automate.",
            dtf_path,
        )
        return False

    def wait_for_output(
        self,
        output_path: str | Path,
        timeout_seconds: int = 300,
        poll_interval: int = 5,
    ) -> bool:
        """Poll for the DTF output file to appear (future integration point).

        Args:
            output_path: Expected output CSV path.
            timeout_seconds: Maximum wait time in seconds.
            poll_interval: Seconds between existence checks.

        Returns:
            True if the file appeared with non-zero size, False if timed out.
        """
        path = Path(output_path)
        elapsed = 0
        while elapsed < timeout_seconds:
            if path.exists() and path.stat().st_size > 0:
                return True
            time.sleep(poll_interval)
            elapsed += poll_interval
        return False
