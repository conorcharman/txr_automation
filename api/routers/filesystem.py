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

from api.schemas.filesystem import (
    BrowseResponse,
    FilesystemEntry,
    ResolvedPaths,
    ResolvePathsRequest,
)

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


# ---------------------------------------------------------------------------
# Smart path resolution
# ---------------------------------------------------------------------------

_STAGE_DIRS = ("kaizen", "extracts", "templates", "output", "logs")


@router.post("/resolve-paths", response_model=ResolvedPaths)
async def resolve_paths(body: ResolvePathsRequest) -> ResolvedPaths:
    """Derive standard directory paths from a fiscal year and quarter.

    Creates the directory tree under
    ``/app/data/{fiscal_year}/{quarter}/{module}/`` (when a module is given) or
    ``/app/data/{fiscal_year}/{quarter}/`` (when no module is supplied), then
    returns the resolved paths.  Any per-stage overrides supplied in the
    request body take precedence over the default layout.

    Args:
        body: Request containing ``fiscal_year``, ``quarter``, optional
            ``module``, and optional ``overrides`` dict.

    Returns:
        A ``ResolvedPaths`` response with the root and per-stage paths.

    Raises:
        HTTPException 400: If the fiscal year, quarter, or module format is
            invalid, or if override paths contain traversal sequences.
        HTTPException 403: If any override path resolves outside allowed roots.
    """
    fy = body.fiscal_year.strip()
    quarter = body.quarter.strip()
    module = body.module.strip() if body.module else None

    if not fy or not quarter:
        raise HTTPException(status_code=400, detail="fiscal_year and quarter are required.")

    # Reject path traversal in the FY/Q/module segments themselves.
    for segment in filter(None, (fy, quarter, module)):
        if ".." in segment or "/" in segment or "\\" in segment:
            raise HTTPException(
                status_code=400,
                detail="Invalid fiscal year, quarter, or module value.",
            )

    quarter_root = Path("/app/data") / fy / quarter
    root = quarter_root / module if module else quarter_root
    paths: dict[str, str] = {}

    for stage in _STAGE_DIRS:
        override = (body.overrides or {}).get(stage)
        if override:
            override_path = Path(override)
            if not override_path.is_absolute():
                raise HTTPException(
                    status_code=400,
                    detail=f"Override path for '{stage}' must be absolute.",
                )
            if ".." in str(override_path).split("/"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Path traversal not allowed in '{stage}' override.",
                )
            resolved_override = override_path.resolve()
            if not _is_allowed(resolved_override):
                raise HTTPException(
                    status_code=403,
                    detail=f"Override path for '{stage}' is outside allowed roots.",
                )
            paths[stage] = str(resolved_override)
        else:
            paths[stage] = str(root / stage)

    # Create all directories (including the root).
    for dir_path in paths.values():
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    return ResolvedPaths(
        root=str(root),
        kaizen=paths["kaizen"],
        extracts=paths["extracts"],
        templates=paths["templates"],
        output=paths["output"],
        logs=paths["logs"],
    )
