"""
Filesystem Router
=================

Provides a read-only endpoint for browsing directories on the server,
used by the frontend's path-picker component.

Security:
    Only directories under an explicit allow-list may be browsed.
    Symlinks that resolve outside the allow-list are rejected.

Endpoints:
    GET /api/filesystem/browse?path=<abs_path>
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from api.schemas.filesystem import BrowseResponse, FilesystemEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filesystem", tags=["filesystem"])

# Allowed root directories (container paths).  Any path must resolve to
# a descendant of one of these to be browseable.
_ALLOWED_ROOTS: list[Path] = [
    Path("/app/data"),
    Path("/app/config"),
    Path("/app/src"),
]


def _is_allowed(resolved: Path) -> bool:
    """Check whether *resolved* is inside one of the allowed roots."""
    return any(
        resolved == root or root in resolved.parents
        for root in _ALLOWED_ROOTS
    )


@router.get("/browse", response_model=BrowseResponse)
async def browse_directory(
    path: str = Query(
        default="/app/data",
        description="Absolute directory path to list.",
    ),
) -> BrowseResponse:
    """List the contents of a server-side directory.

    Args:
        path: The absolute directory path to browse.

    Returns:
        A ``BrowseResponse`` containing the resolved path, its parent,
        and the directory entries sorted alphabetically (directories first).

    Raises:
        HTTPException 400: If the path is relative.
        HTTPException 403: If the path is outside the allowed roots.
        HTTPException 404: If the path does not exist or is not a directory.
    """
    target = Path(path)

    if not target.is_absolute():
        raise HTTPException(status_code=400, detail="Path must be absolute.")

    try:
        resolved = target.resolve(strict=True)
    except OSError:
        raise HTTPException(status_code=404, detail="Path does not exist.")

    if not _is_allowed(resolved):
        raise HTTPException(
            status_code=403,
            detail="Browsing is restricted to /app/data, /app/config, and /app/src.",
        )

    if not resolved.is_dir():
        raise HTTPException(status_code=404, detail="Path is not a directory.")

    # Build parent link (only if parent is still within an allowed root).
    parent: str | None = None
    if _is_allowed(resolved.parent) and resolved.parent != resolved:
        parent = str(resolved.parent)

    entries: list[FilesystemEntry] = []
    try:
        for child in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            # Skip hidden files/directories and ensure symlinks stay in bounds.
            if child.name.startswith("."):
                continue
            try:
                child_resolved = child.resolve(strict=True)
            except OSError:
                continue
            if not _is_allowed(child_resolved):
                continue
            entries.append(
                FilesystemEntry(
                    name=child.name,
                    path=str(child_resolved),
                    is_dir=child_resolved.is_dir(),
                )
            )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied.")

    return BrowseResponse(current=str(resolved), parent=parent, entries=entries)
