"""
File Discovery Module
=====================

Glob-based file discovery utilities.

This is the canonical location for file discovery.
For backward compatibility, this is also re-exported from:
- common.utils
- txr_replay_core.utils
"""

import glob
import os
from typing import Optional, List


class FileDiscovery:
    """
    Unified file discovery with glob patterns.
    
    Provides utilities for finding files using patterns,
    particularly useful for dynamic file discovery.
    
    Example:
        >>> FileDiscovery.find_latest_file("./data", "UnaVista_*.csv")
        './data/UnaVista_MiFIR_Manual_Corrections_2025Q3.csv'
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
