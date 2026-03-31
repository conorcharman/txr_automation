#!/usr/bin/env python3
"""
ScriptRunnerWorker
==================

Runs a script's main() function in a background QThread, redirecting
stdout/stderr to Qt signals that feed the log viewer widget.

Catches SystemExit (from argparse / sys.exit) and converts it to a
signal rather than terminating the application.
"""

import sys
from types import ModuleType
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Signal


class SignalStream(QObject):
    """Wraps a Qt signal as a file-like object for stdout/stderr."""

    text_written = Signal(str)

    def write(self, text: str) -> None:
        """Emit non-empty text via signal."""
        if text and text.strip():
            self.text_written.emit(text)

    def flush(self) -> None:
        """No-op flush for compatibility."""
        pass


class ScriptRunnerWorker(QThread):
    """Runs a script main() function in a background thread."""

    output_line = Signal(str)
    finished_signal = Signal(int)
    error = Signal(str)

    def __init__(
        self,
        script_module: ModuleType,
        argv: List[str],
        parent: Optional[QObject] = None,
    ) -> None:
        """
        Initialise the worker.

        Args:
            script_module: The module containing a main() function.
            argv: Command-line arguments to pass (excluding program name).
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._module = script_module
        self._argv = argv
        self._cancelled = False
        self._exit_code = 1
        # Emit finished_signal only after run() has fully returned and the
        # thread has stopped.  This avoids the race where _on_finished drops
        # the last reference to this QThread while run() is still unwinding.
        self.finished.connect(self._emit_exit_code)

    def _emit_exit_code(self) -> None:
        """Forward the stored exit code via finished_signal."""
        self.finished_signal.emit(self._exit_code)

    def run(self) -> None:
        """Execute script.main() with redirected stdout/stderr."""
        stream = SignalStream()
        stream.text_written.connect(self.output_line.emit)

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        old_argv = sys.argv

        try:
            sys.stdout = stream
            sys.stderr = stream
            sys.argv = [self._module.__name__] + self._argv
            self._module.main()
            self._exit_code = 0
        except SystemExit as e:
            self._exit_code = e.code if isinstance(e.code, int) else 1
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")
            self._exit_code = 1
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sys.argv = old_argv

    def cancel(self) -> None:
        """Request cancellation (best-effort thread termination)."""
        self._cancelled = True
        self.terminate()
