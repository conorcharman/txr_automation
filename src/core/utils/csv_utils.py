"""
CSV Utilities Module
====================

Safe CSV file operations with encoding detection.

This is the canonical location for CSV utilities.
For backward compatibility, this is also re-exported from:
- common.utils
- txr_replay_core.utils
"""

from pathlib import Path
from typing import TextIO, Tuple


def safe_open_csv(file_path: Path, mode: str = 'r', **kwargs) -> Tuple[TextIO, str]:
    """
    Open a CSV file with automatic encoding detection using fallback strategy.
    
    Tries encodings in order: UTF-8, UTF-8-sig (with BOM), Latin-1 (ISO-8859-1).
    This handles files from different sources (modern UTF-8, Excel exports, legacy systems).
    
    Args:
        file_path: Path to the CSV file
        mode: File open mode ('r' for read, 'w' for write)
        **kwargs: Additional arguments passed to open() (e.g., newline='')
        
    Returns:
        Tuple of (file_handle, encoding_used)
        
    Raises:
        UnicodeDecodeError: If file cannot be decoded with any supported encoding
        
    Example:
        >>> f, encoding = safe_open_csv(Path('data.csv'), newline='')
        >>> reader = csv.DictReader(f)
        >>> # ... process file ...
        >>> f.close()
        
    Note:
        For write mode, defaults to UTF-8. For read mode, tries multiple encodings.
    """
    # For write mode, just use UTF-8
    if 'w' in mode or 'a' in mode:
        encoding = kwargs.pop('encoding', 'utf-8')
        return open(file_path, mode, encoding=encoding, **kwargs), encoding
    
    # For read mode, try multiple encodings
    encodings = ['utf-8', 'utf-8-sig', 'latin-1']
    last_error = None
    
    for encoding in encodings:
        try:
            f = open(file_path, mode, encoding=encoding, **kwargs)
            # Try reading first line to validate encoding
            pos = f.tell()
            f.readline()
            f.seek(pos)  # Reset to original position
            return f, encoding
        except (UnicodeDecodeError, UnicodeError) as e:
            if 'f' in locals() and not f.closed:
                f.close()
            last_error = e
            continue
    
    # If all encodings fail, raise error with details
    raise UnicodeDecodeError(
        'utf-8', b'', 0, 1,
        f"Could not decode {file_path} with any encoding: {encodings}. Last error: {last_error}"
    )
