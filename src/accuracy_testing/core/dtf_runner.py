#!/usr/bin/env python3
"""
DTF Runner
==========

Generates and executes System i Data Transfer (.dtf) configuration files
for period-based SQL extraction.

Execution is performed by calling ``cwbodtfx.exe`` (IBM i Access for Windows)
directly via subprocess — no Power Automate dependency is required.

The executable is located automatically from the standard IBM i Access
installation paths.  Override with the ``CWBODTFX_PATH`` environment variable
if your installation is non-standard.

Version 1.1 Changes:
- Implement execute_dtf() via cwbodtfx.exe subprocess — removes Power Automate dependency
- Add _find_cwbodtfx() helper with environment variable override

Version 1.0 Changes:
- Initial implementation for Phase 4 period-based extraction
"""
from __future__ import annotations

import logging
import os
import subprocess
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

    def execute_dtf(self, dtf_path: str | Path, timeout: int = 300) -> bool:
        """Execute a DTF file using System i Data Transfer (cwbodtfx.exe).

        Locates ``cwbodtfx.exe`` from standard IBM i Access installation
        paths or the ``CWBODTFX_PATH`` environment variable, then launches
        the data transfer as a blocking subprocess.

        Args:
            dtf_path: Path to the ``.dtf`` configuration file.
            timeout: Maximum seconds to wait for the process to complete.

        Returns:
            ``True`` if ``cwbodtfx.exe`` exited with return code 0,
            ``False`` if the executable is not found or the process failed.
        """
        _log = logging.getLogger(__name__)
        exe = self._find_cwbodtfx()
        if exe is None:
            _log.error(
                "cwbodtfx.exe not found. Install IBM i Access for Windows or set "
                "the CWBODTFX_PATH environment variable to the full executable path."
            )
            return False

        dtf_abs = str(Path(dtf_path).resolve())
        cmd = [exe, f"/TFRDFN:{dtf_abs}"]
        _log.info("Launching DTF transfer: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            _log.error("DTF transfer timed out after %d seconds: %s", timeout, dtf_abs)
            return False
        except OSError as exc:
            _log.error("Failed to launch cwbodtfx.exe: %s", exc)
            return False

        if result.returncode != 0:
            _log.error(
                "DTF transfer failed (rc=%d). stderr: %s",
                result.returncode,
                result.stderr.strip(),
            )
            return False

        _log.info("DTF transfer completed successfully: %s", dtf_abs)
        return True

    @staticmethod
    def _find_cwbodtfx() -> str | None:
        """Locate cwbodtfx.exe from standard paths or environment override.

        Checks, in order:
        1. ``CWBODTFX_PATH`` environment variable (full path to the exe).
        2. ``C:\\Program Files (x86)\\IBM\\Client Access\\cwbodtfx.exe``
        3. ``C:\\Program Files\\IBM\\Client Access\\cwbodtfx.exe``

        Returns:
            Full path string if found, ``None`` otherwise.
        """
        env_path = os.environ.get("CWBODTFX_PATH")
        if env_path and Path(env_path).is_file():
            return env_path

        candidates = [
            Path("C:/Program Files (x86)/IBM/Client Access/cwbodtfx.exe"),
            Path("C:/Program Files/IBM/Client Access/cwbodtfx.exe"),
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return None

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
