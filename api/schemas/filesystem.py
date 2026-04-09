"""
Filesystem Schemas
==================

Pydantic v2 schemas for the server-side filesystem browse endpoint.
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
