"""
Data Structures Module
======================

Common dataclasses used across all TXR automation scripts.
Includes structures for replay processing and accuracy testing.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class ReplayRecord:
    """
    Universal replay record structure.
    
    This dataclass represents a client record from replay files,
    supporting multiple record types (Phase 2, Phase 3 IDs, Phase 3 Names).
    """
    record_type: str  # 'phase2', 'phase3_ids', 'phase3_names', 'phase3_final'
    transaction_reference: Optional[str] = None
    client_id: Optional[str] = None
    first_name: Optional[str] = None
    surname: Optional[str] = None
    date_of_birth: Optional[str] = None
    incident_codes: List[str] = field(default_factory=list)
    corrections: Dict[str, str] = field(default_factory=dict)
    original_row: List[str] = field(default_factory=list)
    row_index: int = 0
    source_file: str = ""
    file_type: str = ""  # 'single', 'combined', 'IDs', 'Names', etc.
    all_ids: List[str] = field(default_factory=list)
    
    def __repr__(self) -> str:
        """Readable representation for debugging"""
        return (
            f"ReplayRecord(type={self.record_type}, "
            f"txn_ref={self.transaction_reference}, "
            f"client_id={self.client_id}, "
            f"name={self.first_name} {self.surname}, "
            f"incident_codes={self.incident_codes})"
        )


@dataclass
class LookupResult:
    """
    Universal lookup result structure.
    
    Represents the result of looking up a transaction or client
    in incident files or UnaVista data.
    """
    found: bool
    correction: str = ""
    correction_field: str = ""
    error_flag: str = ""
    transaction_ref: str = ""
    match_type: str = ""  # 'id_buyer', 'id_seller', 'name_buyer', 'name_seller', etc.
    
    def __repr__(self) -> str:
        """Readable representation for debugging"""
        if not self.found:
            return "LookupResult(found=False)"
        return (
            f"LookupResult(found=True, match_type={self.match_type}, "
            f"correction={self.correction[:50]}...)"
        )


@dataclass
class UnaVistaTransaction:
    """
    UnaVista transaction record.
    
    Represents a single transaction from UnaVista export files.
    """
    transaction_ref: str
    row_data: List[str]
    row_index: int
    
    def get_field(self, index: int, default: str = "") -> str:
        """Safely get field value by index"""
        if index < len(self.row_data):
            return self.row_data[index].strip()
        return default
    
    def __repr__(self) -> str:
        """Readable representation for debugging"""
        return f"UnaVistaTransaction(ref={self.transaction_ref}, row_index={self.row_index})"


@dataclass
class ProcessingStats:
    """
    Standardized statistics tracking.
    
    Used to track processing statistics consistently across all scripts.
    """
    processed_files: int = 0
    processed_records: int = 0
    successful_matches: int = 0
    not_found: int = 0
    no_corrections: int = 0
    inconsistent_corrections: int = 0
    errors: int = 0
    custom_stats: Dict[str, Any] = field(default_factory=dict)
    
    def increment(self, stat_name: str, amount: int = 1) -> None:
        """Increment a statistic by amount"""
        if hasattr(self, stat_name):
            setattr(self, stat_name, getattr(self, stat_name) + amount)
        else:
            if stat_name not in self.custom_stats:
                self.custom_stats[stat_name] = 0
            self.custom_stats[stat_name] += amount
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary"""
        base_stats = {
            'processed_files': self.processed_files,
            'processed_records': self.processed_records,
            'successful_matches': self.successful_matches,
            'not_found': self.not_found,
            'no_corrections': self.no_corrections,
            'inconsistent_corrections': self.inconsistent_corrections,
            'errors': self.errors,
        }
        base_stats.update(self.custom_stats)
        return base_stats
    
    def __repr__(self) -> str:
        """Readable representation for debugging"""
        return (
            f"ProcessingStats("
            f"records={self.processed_records}, "
            f"matches={self.successful_matches}, "
            f"not_found={self.not_found}, "
            f"errors={self.errors})"
        )
