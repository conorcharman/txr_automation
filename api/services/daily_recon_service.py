"""
Daily Reconciliation Service
=============================

Async service layer for daily_recon domain CRUD and orchestration.
Stateless; session-injected via Depends(get_db).

Usage:
    from api.services.daily_recon_service import daily_recon_service
    from api.database import get_db

    async def route(db: AsyncSession = Depends(get_db)):
        runs = await daily_recon_service.list_runs(db)
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from api.models.daily_recon import (
    ReconCell,
    ReconCellIssue,
    ReconRow,
    ReconRun,
)


class DailyReconService:
    """Service for daily reconciliation operations."""

    async def list_runs(
        self,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReconRun]:
        """List reconciliation runs (paginated).

        Args:
            db: Async database session.
            limit: Max rows to return.
            offset: Rows to skip.

        Returns:
            List of ReconRun instances.
        """
        result = await db.execute(
            select(ReconRun)
            .order_by(ReconRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_run(self, db: AsyncSession, run_id: UUID) -> ReconRun | None:
        """Fetch a single run by ID.

        Args:
            db: Async database session.
            run_id: The run UUID.

        Returns:
            The ReconRun instance, or None if not found.
        """
        result = await db.execute(select(ReconRun).where(ReconRun.id == run_id))
        return result.scalar_one_or_none()

    async def create_run(
        self,
        db: AsyncSession,
        job_id: UUID | None = None,
        source_query: str = "",
    ) -> ReconRun:
        """Create a new reconciliation run.

        Args:
            db: Async database session.
            job_id: Optional Celery job ID.
            source_query: The SQL query executed (for audit).

        Returns:
            The newly created ReconRun instance.
        """
        run = ReconRun(
            job_id=job_id,
            source_query=source_query,
            status="pending",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    async def update_run_status(
        self,
        db: AsyncSession,
        run_id: UUID,
        status: str,
    ) -> ReconRun | None:
        """Update run status.

        Args:
            db: Async database session.
            run_id: The run UUID.
            status: New status string.

        Returns:
            Updated ReconRun, or None if not found.
        """
        run = await self.get_run(db, run_id)
        if run is None:
            return None
        run.status = status
        run.updated_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(run)
        return run

    async def list_rows(
        self,
        db: AsyncSession,
        run_id: UUID,
        limit: int = 50,
        offset: int = 0,
        errored_only: bool = False,
    ) -> list[ReconRow]:
        """List rows in a run (optionally filtered by error status).

        Args:
            db: Async database session.
            run_id: The parent run UUID.
            limit: Max rows to return.
            offset: Rows to skip.
            errored_only: If True, return only rows with has_error=True.

        Returns:
            List of ReconRow instances.
        """
        stmt = (
            select(ReconRow)
            .where(ReconRow.run_id == run_id)
            .options(joinedload(ReconRow.cells))
        )
        if errored_only:
            stmt = stmt.where(ReconRow.has_error.is_(True))
        stmt = stmt.order_by(ReconRow.row_index).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_row(self, db: AsyncSession, row_id: UUID) -> ReconRow | None:
        """Fetch a single row with all its cells.

        Args:
            db: Async database session.
            row_id: The row UUID.

        Returns:
            The ReconRow instance, or None if not found.
        """
        result = await db.execute(
            select(ReconRow)
            .where(ReconRow.id == row_id)
            .options(joinedload(ReconRow.cells).joinedload(ReconCell.issues))
        )
        return result.unique().scalar_one_or_none()

    async def get_cell(self, db: AsyncSession, cell_id: int) -> ReconCell | None:
        """Fetch a single cell with issues.

        Args:
            db: Async database session.
            cell_id: The cell bigint ID.

        Returns:
            The ReconCell instance, or None if not found.
        """
        result = await db.execute(
            select(ReconCell)
            .where(ReconCell.id == cell_id)
            .options(joinedload(ReconCell.issues))
        )
        return result.scalar_one_or_none()

    async def apply_correction(
        self,
        db: AsyncSession,
        cell_id: int,
        corrected_value: str,
    ) -> ReconCell | None:
        """Apply a manual correction to a cell (user edit).

        Does not auto-approve; just saves the corrected value.

        Args:
            db: Async database session.
            cell_id: The cell ID.
            corrected_value: The corrected value to store.

        Returns:
            Updated ReconCell, or None if not found.
        """
        cell = await self.get_cell(db, cell_id)
        if cell is None:
            return None
        cell.corrected_value = corrected_value
        cell.updated_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(cell)
        return cell

    async def accept_suggestion(
        self,
        db: AsyncSession,
        cell_id: int,
    ) -> ReconCell | None:
        """Accept a suggested fix (copy suggested_fix -> corrected_value).

        Args:
            db: Async database session.
            cell_id: The cell ID.

        Returns:
            Updated ReconCell, or None if not found, or if no suggestion.
        """
        cell = await self.get_cell(db, cell_id)
        if cell is None or cell.suggested_fix is None:
            return None
        cell.corrected_value = cell.suggested_fix
        cell.updated_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(cell)
        return cell

    async def approve_row(
        self,
        db: AsyncSession,
        row_id: UUID,
    ) -> ReconRow | None:
        """Mark a row as approved.

        Args:
            db: Async database session.
            row_id: The row UUID.

        Returns:
            Updated ReconRow, or None if not found.
        """
        row = await self.get_row(db, row_id)
        if row is None:
            return None
        row.approved = True
        row.approved_at = datetime.now(tz=timezone.utc)
        row.updated_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(row)
        return row

    async def unapprove_row(
        self,
        db: AsyncSession,
        row_id: UUID,
    ) -> ReconRow | None:
        """Unmark a row as approved.

        Args:
            db: Async database session.
            row_id: The row UUID.

        Returns:
            Updated ReconRow, or None if not found.
        """
        row = await self.get_row(db, row_id)
        if row is None:
            return None
        row.approved = False
        row.approved_at = None
        row.updated_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(row)
        return row

    async def delete_run(
        self,
        db: AsyncSession,
        run_id: UUID,
    ) -> bool:
        """Delete a reconciliation run and all cascading rows/cells/issues.

        Args:
            db: Async database session.
            run_id: The run UUID.

        Returns:
            True if deleted, False if not found.
        """
        run = await self.get_run(db, run_id)
        if run is None:
            return False
        await db.delete(run)
        await db.commit()
        return True


#: Module-level singleton for use in route handlers via dependency injection.
daily_recon_service = DailyReconService()

