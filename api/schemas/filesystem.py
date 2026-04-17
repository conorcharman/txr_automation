"""
Filesystem Schemas
==================

Pydantic v2 schemas for the server-side filesystem browse endpoint
and the smart path resolution endpoint.
"""

from api.schemas.common import _CamelModel


class FilesystemEntry(_CamelModel):
    """A single entry in a directory listing.

    Attributes:
        name: The file or directory name (basename only).
        path: The full absolute path on the server.
        is_dir: ``True`` for directories, ``False`` for files.
    """

    name: str
    path: str
    is_dir: bool


class BrowseResponse(_CamelModel):
    """Response body for the filesystem browse endpoint.

    Attributes:
        current: The resolved absolute path being listed.
        parent: The parent directory path, or ``None`` if at a root boundary.
        entries: List of files and directories inside ``current``.
    """

    current: str
    parent: str | None = None
    entries: list[FilesystemEntry]


# ---------------------------------------------------------------------------
# Smart path resolution
# ---------------------------------------------------------------------------


class ResolvePathsRequest(_CamelModel):
    """Request body for resolving standard directory paths from FY and quarter.

    Attributes:
        fiscal_year: Fiscal year string, e.g. ``"FY26"``.
        quarter: Quarter string, e.g. ``"Q1"``.
        module: Optional module sub-directory inserted between the quarter and
            the stage dirs, e.g. ``"accuracy_testing"`` or ``"replay"``.  When
            omitted the stage dirs are placed directly under the quarter root.
        overrides: Optional per-stage path overrides. Keys must be one of
            ``extracts``, ``templates``, ``output``, ``logs``.
    """

    fiscal_year: str
    quarter: str
    module: str | None = None
    overrides: dict[str, str] | None = None


class ResolvedPaths(_CamelModel):
    """Resolved directory paths for a given FY/Q combination.

    Attributes:
        root: The base directory for stage sub-directories, e.g.
            ``"/app/data/FY26/Q1/accuracy_testing"`` when a module is given,
            or ``"/app/data/FY26/Q1"`` when no module is supplied.
        extracts: Path to the extracts sub-directory.
        templates: Path to the templates sub-directory.
        output: Path to the output sub-directory.
        logs: Path to the logs sub-directory.
    """

    root: str
    kaizen: str
    extracts: str
    templates: str
    output: str
    logs: str
