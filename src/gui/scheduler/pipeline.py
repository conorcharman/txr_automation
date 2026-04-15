#!/usr/bin/env python3
"""
PipelineExecutor (Legacy Stub)
==============================

In version 1.x this module executed pipeline steps locally via subprocess.
Since version 2.0 all pipeline execution is delegated to the FastAPI backend
via ``gui.api.pipeline`` and ``gui.workers.api_worker.ApiWorker``.

This module is retained only for backwards compatibility with existing
imports.  No local execution code remains.

Version 2.0 Changes:
- Removed all subprocess-based step execution
- Removed DTFRunner integration
- Class kept as empty stub to avoid ImportError in existing code
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PipelineExecutor:
    """Legacy stub — all execution is now API-backed.

    .. deprecated::
        Use ``gui.api.pipeline.trigger_pipeline()`` and ``ApiWorker``
        instead of calling this class directly.
    """

    def execute(self, config: object) -> None:
        """No-op.  Raises ``NotImplementedError``.

        Args:
            config: Unused.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "Local pipeline execution has been removed. "
            "Use the API backend (POST /api/pipelines/{id}/trigger) instead."
        )
