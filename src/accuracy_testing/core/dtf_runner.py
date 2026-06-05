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
                If a Linux path is detected (e.g., /app/data), it is converted
                to a Windows UNC or local path for IBM Data Transfer compatibility.
            dtf_output_path: Where to save the generated .dtf file.
            template_path: Override the default template path.

        Returns:
            Path to the generated DTF file.
        """
        template = Path(template_path or self.TEMPLATE_PATH)
        content = template.read_text(encoding="utf-8")
        
        # Convert Linux paths to Windows paths for DTF compatibility.
        # IBM Data Transfer runs on Windows and needs Windows-format paths.
        dtf_output_path_for_dtf = self._convert_path_to_windows(str(output_csv_path))
        
        content = content.replace("{OUTPUT_PATH}", dtf_output_path_for_dtf)
        content = content.replace("{SQL_QUERY}", self._flatten_sql(sql_query))
        output = Path(dtf_output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        return output

    @staticmethod
    def _flatten_sql(sql: str) -> str:
        """Collapse a multi-line SQL string to a single line suitable for the
        ``SQLSelect=`` field of a DTF INI file.

        The DTF format is an INI file — multi-line values are not supported.
        This method strips ``--`` comments, collapses newlines, and normalises
        whitespace so the entire statement fits on one line.

        Args:
            sql: Raw SQL text, potentially with comments and newlines.

        Returns:
            Single-line SQL string.
        """
        import re

        lines = sql.splitlines()
        # Remove full-line and inline -- comments
        stripped = [re.sub(r"--.*", "", line) for line in lines]
        # Join and collapse whitespace
        flat = " ".join(stripped)
        return re.sub(r"\s+", " ", flat).strip()

    @staticmethod
    def _convert_path_to_windows(path_str: str) -> str:
        """Convert a Linux container path to a Windows path for DTF compatibility.

        IBM Data Transfer for System i runs on Windows and requires Windows-format
        paths (backslashes and drive letters). This method detects and converts common
        Docker volume mappings to their Windows equivalents.

        Mappings supported (configurable via environment variables):
        - ``/app/data`` → ``DTF_WINDOWS_APP_DATA_PATH`` or auto-detect
        - ``/app`` → ``DTF_WINDOWS_APP_PATH`` or auto-detect

        If the path is already a Windows path, it is returned unchanged.
        If a Linux path cannot be mapped, it is returned as-is (may fail at DTF runtime).

        Args:
            path_str: Path that may be Linux or Windows format.

        Returns:
            Windows-format path string.
        """
        # If already a Windows path (contains backslash or drive letter), return as-is.
        if "\\" in path_str or (len(path_str) > 1 and path_str[1] == ":"):
            return path_str

        # Detect Linux path patterns and map to Windows equivalents.
        if path_str.startswith("/app/data"):
            # Check for environment variable override first.
            win_base = os.environ.get("DTF_WINDOWS_APP_DATA_PATH")
            if win_base:
                # Replace /app/data with the configured Windows path.
                relative = path_str[len("/app/data"):].lstrip("/")
                return (Path(win_base) / relative).as_posix().replace("/", "\\")

            # Auto-detect: common installation pattern.
            # Assume /app/data → C:\Users\<user>\Documents\GitHub\txr_automation\data
            # (or wherever the repo is checked out).
            default_base = r"C:\Users\ccharm\Documents\GitHub\txr_automation\data"
            relative = path_str[len("/app/data"):].lstrip("/")
            return (Path(default_base) / relative).as_posix().replace("/", "\\")

        elif path_str.startswith("/app"):
            # Map /app to the app root.
            win_base = os.environ.get("DTF_WINDOWS_APP_PATH")
            if win_base:
                relative = path_str[len("/app"):].lstrip("/")
                return (Path(win_base) / relative).as_posix().replace("/", "\\")

            # Auto-detect: use repo root + txr_automation.
            default_base = r"C:\Users\ccharm\Documents\GitHub\txr_automation"
            relative = path_str[len("/app"):].lstrip("/")
            return (Path(default_base) / relative).as_posix().replace("/", "\\")

        # For other Linux paths or unmapped patterns, return as-is.
        return path_str

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
        standard IBM i Access installation paths, the Windows registry
        ``.dtf`` file association, or the ``CWBODTFX_PATH`` environment
        variable, then launches the data transfer as a blocking subprocess.

        The batch executor is ``rtopcb.exe`` (IBM System i Access for
        Windows batch data transfer utility).  Override the path with the
        ``CWBODTFX_PATH`` environment variable if your installation is
        non-standard.

        Args:
            dtf_path: Path to the ``.dtf`` configuration file.
            timeout: Maximum seconds to wait for the process to complete.

        Returns:
            ``True`` if ``rtopcb.exe`` exited with return code 0,
            ``False`` if the executable is not found or the process failed.
        """
        _log = logging.getLogger(__name__)
        exe = self._find_cwbodtfx()
        if exe is None:
            _log.error(
                "rtopcb.exe not found. Install IBM i Access for Windows or set "
                "the CWBODTFX_PATH environment variable to the full executable path."
            )
            return False

        dtf_abs = str(Path(dtf_path).resolve())
        cmd = [exe, dtf_abs]
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
            _log.error("Failed to launch rtopcb.exe: %s", exc)
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
        """Locate rtopcb.exe (IBM i Access batch transfer utility) from standard
        paths or an environment variable override.

        ``rtopcb.exe`` is the command-line counterpart to the ``cwbtf.exe``
        GUI editor and accepts ``.dtf`` files directly as a positional
        argument.

        Checks, in order:
        1. ``CWBODTFX_PATH`` environment variable (full path to the exe).
        2. ``C:\\Program Files (x86)\\IBM\\Client Access\\rtopcb.exe``
        3. ``C:\\Program Files\\IBM\\Client Access\\rtopcb.exe``
        4. Windows registry ``.dtf`` file association — resolves the IBM
           Client Access installation directory and looks for ``rtopcb.exe``
           there.

        Returns:
            Full path string if found, ``None`` otherwise.
        """
        env_path = os.environ.get("CWBODTFX_PATH")
        if env_path and Path(env_path).is_file():
            return env_path

        candidates = [
            Path("C:/Program Files (x86)/IBM/Client Access/rtopcb.exe"),
            Path("C:/Program Files/IBM/Client Access/rtopcb.exe"),
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)

        # Fall back to the Windows registry: look up the open command registered
        # for the .dtf file association, then look for rtopcb.exe in the same
        # IBM Client Access installation directory.  The registered command
        # points to cwbtf.exe (the GUI editor) — rtopcb.exe is in the same
        # folder and is the correct batch executor.
        try:
            import winreg  # only available on Windows
            import shlex

            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, r".dtf"
            ) as ext_key:
                prog_id, _ = winreg.QueryValueEx(ext_key, "")

            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT,
                rf"{prog_id}\shell\open\command",
            ) as cmd_key:
                open_cmd, _ = winreg.QueryValueEx(cmd_key, "")

            # The command is typically: C:\PROGRA~2\IBM\CLIENT~1\cwbtf.exe %1
            # Resolve the short path, then look for rtopcb.exe alongside it.
            parts = shlex.split(open_cmd, posix=False)
            registered_exe = Path(parts[0].strip('"')).resolve()
            rtopcb = registered_exe.parent / "rtopcb.exe"
            if rtopcb.is_file():
                return str(rtopcb)
        except Exception:  # noqa: BLE001
            pass

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
