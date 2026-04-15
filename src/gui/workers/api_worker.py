#!/usr/bin/env python3
"""
API Worker
==========

QThread that posts a job to the FastAPI backend, then streams real-time
log output via WebSocket.  Emits the same signals as
``ScriptRunnerWorker`` so it can be used as a drop-in replacement.

Falls back to polling ``GET /api/jobs/{id}`` every 2 seconds if the
WebSocket connection fails.
"""

import json
import logging
import time
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QThread, Signal

from gui.api.client import ApiClient, ApiError

logger = logging.getLogger(__name__)

# Terminal job statuses that indicate the job has finished.
_TERMINAL_STATUSES = frozenset({"success", "failed", "cancelled"})


class ApiWorker(QThread):
    """Post a job to the API and stream logs via WebSocket.

    Signals (identical to ``ScriptRunnerWorker``):
        output_line(str)  — a single log line from the running job.
        finished_signal(int) — exit code: 0 for success, 1 for failure.
        error(str) — error message string.
    """

    output_line = Signal(str)
    finished_signal = Signal(int)
    error = Signal(str)

    def __init__(
        self,
        client: ApiClient,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialise the worker.

        Args:
            client: Configured ``ApiClient`` instance.
            endpoint: API path to POST to, e.g. ``"/api/accuracy/run-incidents"``.
            payload: JSON-serialisable request body.
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._client = client
        self._endpoint = endpoint
        self._payload = payload or {}
        self._cancelled = False
        self._job_id: Optional[str] = None
        self._exit_code = 1

        # Emit finished_signal only after QThread.run() has fully returned,
        # avoiding the race where a connected slot drops the last reference
        # while the thread is still unwinding.
        self.finished.connect(self._emit_exit_code)

    def _emit_exit_code(self) -> None:
        """Forward the stored exit code via ``finished_signal``."""
        self.finished_signal.emit(self._exit_code)

    @property
    def job_id(self) -> Optional[str]:
        """Return the job UUID once the API has responded."""
        return self._job_id

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Post the job and stream logs until completion."""
        try:
            self._submit_job()
            if self._cancelled or self._job_id is None:
                return

            if not self._stream_via_websocket():
                self._poll_until_complete()
        except ApiError as exc:
            self.error.emit(str(exc))
            self._exit_code = 1
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"{type(exc).__name__}: {exc}")
            self._exit_code = 1

    # ------------------------------------------------------------------
    # Step 1: Submit job
    # ------------------------------------------------------------------

    def _submit_job(self) -> None:
        """POST to the endpoint and extract the job ID from the response."""
        try:
            data = self._client.post(self._endpoint, self._payload)
        except Exception as exc:
            self.error.emit(f"Failed to submit job: {exc}")
            self._exit_code = 1
            return

        # The API returns either {"id": "..."} or {"jobId": "..."}.
        self._job_id = (
            data.get("id") or data.get("jobId") if isinstance(data, dict) else None
        )
        if not self._job_id:
            self.error.emit("API did not return a job ID.")
            self._exit_code = 1
            return

        self.output_line.emit(f"Job submitted: {self._job_id}")

    # ------------------------------------------------------------------
    # Step 2a: WebSocket streaming (preferred)
    # ------------------------------------------------------------------

    def _stream_via_websocket(self) -> bool:
        """Attempt to stream logs via WebSocket.

        Returns:
            ``True`` if streaming completed (or the job finished),
            ``False`` if the WebSocket connection could not be established
            and the caller should fall back to polling.
        """
        try:
            import websocket  # websocket-client
        except ImportError:
            logger.debug("websocket-client not installed; falling back to polling.")
            return False

        ws_url = f"{self._client.ws_url}/api/ws/jobs/{self._job_id}/logs"

        try:
            ws = websocket.WebSocket()
            ws.settimeout(5)
            ws.connect(ws_url)
        except Exception:
            logger.debug("WebSocket connection failed; falling back to polling.")
            return False

        try:
            ws.settimeout(2)
            while not self._cancelled:
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                except websocket.WebSocketConnectionClosedException:
                    break

                if not raw:
                    break

                msg = self._parse_ws_message(raw)
                if msg is None:
                    continue

                msg_type = msg.get("type", "log")
                msg_data = msg.get("data", "")

                if msg_type == "status":
                    self._handle_status(msg_data)
                    if msg_data in _TERMINAL_STATUSES:
                        break
                elif msg_type == "waiting":
                    self.output_line.emit(f"\u23f3 {msg_data}")
                else:
                    self.output_line.emit(msg_data)
        finally:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass

        return True

    # ------------------------------------------------------------------
    # Step 2b: Polling fallback
    # ------------------------------------------------------------------

    def _poll_until_complete(self) -> None:
        """Poll ``GET /api/jobs/{id}`` every 2 seconds until the job finishes."""
        self.output_line.emit("(WebSocket unavailable — polling for updates)")
        seen_lines = 0

        while not self._cancelled:
            time.sleep(2)
            try:
                job = self._client.get(f"/api/jobs/{self._job_id}")
            except (ApiError, Exception) as exc:
                self.output_line.emit(f"Polling error: {exc}")
                continue

            status = job.get("status", "")

            # Emit any new log lines from the persisted output.
            log_output = job.get("logOutput") or ""
            lines = log_output.splitlines()
            for line in lines[seen_lines:]:
                self.output_line.emit(line)
            seen_lines = len(lines)

            if status in _TERMINAL_STATUSES:
                self._handle_status(status)
                break

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ws_message(raw: str) -> Optional[Dict[str, Any]]:
        """Parse a raw WebSocket message as JSON.

        Returns:
            Parsed dict, or ``None`` if the message is not valid JSON.
        """
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return {"type": "log", "data": raw}

    def _handle_status(self, status: str) -> None:
        """Set exit code based on terminal status string."""
        if status == "success":
            self.output_line.emit("Job completed successfully.")
            self._exit_code = 0
        elif status == "cancelled":
            self.output_line.emit("Job was cancelled.")
            self._exit_code = 1
        else:
            self.output_line.emit(f"Job finished with status: {status}")
            self._exit_code = 1

    def cancel(self) -> None:
        """Request cancellation of the running job.

        Attempts to cancel the job on the server as well as stopping
        the local log streaming.
        """
        self._cancelled = True
        if self._job_id:
            try:
                self._client.post(f"/api/jobs/{self._job_id}/cancel")
            except Exception:  # noqa: BLE001
                pass
