"""
Utility Functions Module
=========================

Common utility functions used across replay processing scripts.
"""

import glob
import os
from datetime import datetime
from typing import Optional, List


class DateParser:
    """
    Handles various date format parsing with caching.
    
    Extracted from phase_3_processor_v4_2.py and phase_3_final_lookup.py.
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
    particularly useful for dynamic file discovery in Phase 3 Final Lookup.
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
