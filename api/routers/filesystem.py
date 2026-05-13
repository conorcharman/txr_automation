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

from api.config import get_settings
from api.schemas.filesystem import (
    BrowseResponse,
    FileReadResponse,
    FilesystemEntry,
    ResolvedPaths,
    ResolvePathsRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filesystem", tags=["filesystem"])

def _allowed_roots() -> list[Path]:
    """Return the list of allowed root directories, resolved to absolute paths."""
    data_dir = get_settings().data_dir.resolve()
    roots = [data_dir]
    # In Docker the project also mounts /app/config and /app/src; add them
    # if they exist so that Docker deployments are not broken.
    for extra in (Path("/app/config"), Path("/app/src"), Path("/app/data")):
        if extra.exists() and extra not in roots:
            roots.append(extra)
    return roots


def _is_allowed(resolved: Path) -> bool:
    """Check whether *resolved* is inside one of the allowed roots."""
    return any(
        resolved == root or root in resolved.parents
        for root in _allowed_roots()
    )


@router.get("/config")
async def filesystem_config() -> dict[str, str]:
    """Return the resolved data root directory for use by the frontend.

    Returns:
        A dict with ``dataRoot`` set to the resolved absolute path of
        ``settings.data_dir``.
    """
    data_dir = get_settings().data_dir.resolve()
    return {"dataRoot": str(data_dir)}


@router.get("/browse", response_model=BrowseResponse)
async def browse_directory(
    path: str = Query(
        default=None,
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
    # Default to the configured data directory when no path is supplied.
    effective_path = path if path is not None else str(get_settings().data_dir.resolve())
    target = Path(effective_path)

    if not target.is_absolute():
        raise HTTPException(status_code=400, detail="Path must be absolute.")

    try:
        resolved = target.resolve(strict=True)
    except OSError:
        raise HTTPException(status_code=404, detail="Path does not exist.")

    if not _is_allowed(resolved):
        raise HTTPException(
            status_code=403,
            detail="Browsing is restricted to the configured data directory.",
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
# File read
# ---------------------------------------------------------------------------

#: Maximum number of bytes read from a single file.  Files larger than this
#: are truncated and the ``truncated`` flag is set in the response.
_MAX_READ_BYTES: int = 1_048_576  # 1 MiB

#: Encodings attempted in order when reading an unknown text file.
_TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "latin-1")


@router.get("/read", response_model=FileReadResponse)
async def read_file(
    path: str = Query(description="Absolute path of the file to read."),
) -> FileReadResponse:
    """Return the text content of a server-side file.

    Reads up to 1 MiB of content, setting ``truncated=True`` when the file
    is larger.  Attempts UTF-8 decoding first, then falls back to Latin-1 so
    that most log and CSV files can be displayed without error.

    Args:
        path: The absolute file path to read.

    Returns:
        A ``FileReadResponse`` with the file name, size, and decoded content.

    Raises:
        HTTPException 400: If the path is relative.
        HTTPException 403: If the path is outside the allowed roots.
        HTTPException 404: If the path does not exist or is a directory.
        HTTPException 422: If the file cannot be decoded as text.
    """
    target = Path(path)

    if not target.is_absolute():
        raise HTTPException(status_code=400, detail="Path must be absolute.")

    try:
        resolved = target.resolve(strict=True)
    except OSError:
        raise HTTPException(status_code=404, detail="File does not exist.")

    if not _is_allowed(resolved):
        raise HTTPException(
            status_code=403,
            detail="Reading is restricted to the configured data directory.",
        )

    if resolved.is_dir():
        raise HTTPException(status_code=404, detail="Path is a directory, not a file.")

    size_bytes = resolved.stat().st_size
    truncated = size_bytes > _MAX_READ_BYTES

    raw = resolved.read_bytes()[:_MAX_READ_BYTES]

    content: str | None = None
    for enc in _TEXT_ENCODINGS:
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        raise HTTPException(
            status_code=422,
            detail="File does not appear to be a text file.",
        )

    return FileReadResponse(
        path=str(resolved),
        name=resolved.name,
        size_bytes=size_bytes,
        content=content,
        truncated=truncated,
    )


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

    quarter_root = get_settings().data_dir.resolve() / fy / quarter
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
