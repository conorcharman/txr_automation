"""
Country Codes Reference Data
=============================

BACKWARD COMPATIBILITY MODULE
-----------------------------
This module now re-exports from the canonical location: core.data.country_codes

All classes and data are maintained for backward compatibility.
New code should import directly from core.data:
    from core.data import country_manager, Country, CountryDataManager, COUNTRIES

Data source: ISO 3166-1 country codes (249 countries)
"""

# Try different import paths for flexibility (installed package vs development)
try:
    # When imported as installed package (accuracy_testing.core.country_codes)
    from core.data.country_codes import (
        COUNTRIES,
        Country,
        CountryDataManager,
        country_manager,
    )
except ImportError:
    # When imported from workspace root (src.accuracy_testing.core.country_codes)
    from src.core.data.country_codes import (
        COUNTRIES,
        Country,
        CountryDataManager,
        country_manager,
    )

__all__ = [
    "Country",
    "CountryDataManager",
    "country_manager",
    "COUNTRIES",
]
