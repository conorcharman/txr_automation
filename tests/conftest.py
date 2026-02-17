"""
Pytest configuration for test suite.

This adds the project root to sys.path to allow imports from src.
"""

import sys
from pathlib import Path

# Add project root to path for src.* imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
