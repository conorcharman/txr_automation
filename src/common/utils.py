"""
Utility Functions Module
=========================

Common utility functions used across replay and accuracy testing modules.
"""

import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, TextIO, Tuple


class DateParser:
    """
    Handles various date format parsing with caching.
    
    This unified implementation includes support for:
    - Multiple date formats (DD/MM/YYYY, YYYY-MM-DD, etc.)
    - Timestamp handling (strips time portions)
    - Caching for performance
    """
    
    _date_cache = {}  # Cache parsed dates for performance
    
    @classmethod
    def parse_date(cls, date_str: str) -> Optional[str]:
        """
        Parse date with caching for performance.
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            Standardized date string (YYYY-MM-DD) or None if parsing fails
            
        Examples:
            >>> DateParser.parse_date("01/12/2023")
            '2023-12-01'
            >>> DateParser.parse_date("2023-12-01")
            '2023-12-01'
            >>> DateParser.parse_date("01/12/2023 14:30:00")
            '2023-12-01'
        """
        if not date_str or date_str.strip() == "":
            return None
            
        date_str = date_str.strip()
        
        # Check cache first
        if date_str in cls._date_cache:
            return cls._date_cache[date_str]
        
        # Strip time portion if present (e.g., "08/09/1984 00:00:00" -> "08/09/1984")
        if ' ' in date_str:
            parts = date_str.split(' ', 1)
            time_part = parts[1].strip()
            # Check if second part looks like time (contains : or is all digits)
            if ':' in time_part or time_part.replace(':', '').isdigit():
                date_str = parts[0]  # Use only the date portion
        
        # Common date formats to try
        date_formats = [
            '%Y-%m-%d',  # YYYY-MM-DD (ISO format)
            '%d/%m/%Y',  # DD/MM/YYYY (UK format)
            '%m/%d/%Y',  # MM/DD/YYYY (US format)
            '%d-%m-%Y',  # DD-MM-YYYY
            '%m-%d-%Y',  # MM-DD-YYYY
            '%Y/%m/%d',  # YYYY/MM/DD
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                result = parsed_date.strftime('%Y-%m-%d')
                cls._date_cache[date_str] = result
                return result
            except ValueError:
                continue
        
        # Cache miss result too (avoid repeated parsing attempts)
        cls._date_cache[date_str] = None
        return None
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the date parsing cache"""
        cls._date_cache.clear()
    
    @classmethod
    def cache_size(cls) -> int:
        """Get current cache size"""
        return len(cls._date_cache)


class CharacterReplacement:
    """
    Handle special character replacements for output files.
    
    Used primarily in Phase 2 processing where colons in corrections
    need to be replaced with the NOT SIGN character (¬) for compatibility.
    """
    
    @staticmethod
    def colon_to_not_sign(value: str) -> str:
        """
        Replace colons with NOT SIGN character (¬).
        
        Args:
            value: String value to process
            
        Returns:
            String with colons replaced by chr(172) (¬)
            
        Note:
            Using chr(172) instead of Unicode to prevent encoding issues.
            Returns original value unchanged if it's a special marker.
        """
        if not value or value in ["No Change", "Client not found", "Processing Error"]:
            return value
        # Use ASCII character replacement to avoid encoding issues
        return value.replace(':', chr(172))  # chr(172) = ¬ (NOT SIGN)
    
    @staticmethod
    def not_sign_to_colon(value: str) -> str:
        """
        Reverse replacement: NOT SIGN back to colon.
        
        Args:
            value: String value to process
            
        Returns:
            String with NOT SIGN replaced by colons
        """
        if not value:
            return value
        return value.replace(chr(172), ':')


class FileDiscovery:
    """
    Unified file discovery with glob patterns.
    
    Provides utilities for finding files using patterns,
    particularly useful for dynamic file discovery.
    """
    
    @staticmethod
    def find_latest_file(directory: str, pattern: str) -> Optional[str]:
        """
        Find most recent file matching pattern.
        
        Args:
            directory: Directory to search in
            pattern: Glob pattern (e.g., "*.csv", "UnaVista_*.csv")
            
        Returns:
            Path to most recent matching file, or None if no matches
            
        Example:
            >>> FileDiscovery.find_latest_file("./data", "UnaVista_*.csv")
            './data/UnaVista_MiFIR_Manual_Corrections_2025Q3.csv'
        """
        matches = glob.glob(os.path.join(directory, pattern))
        if matches:
            # Return the file with the most recent modification time
            return max(matches, key=os.path.getmtime)
        return None
    
    @staticmethod
    def find_all_files(directory: str, pattern: str) -> List[str]:
        """
        Find all files matching pattern.
        
        Args:
            directory: Directory to search in
            pattern: Glob pattern
            
        Returns:
            List of matching file paths (empty list if no matches)
        """
        return glob.glob(os.path.join(directory, pattern))
    
    @staticmethod
    def ensure_directory_exists(directory: str) -> None:
        """
        Create directory if it doesn't exist.
        
        Args:
            directory: Directory path to create
        """
        os.makedirs(directory, exist_ok=True)


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
