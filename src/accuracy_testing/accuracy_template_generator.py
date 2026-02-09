"""
Accuracy Testing Template Generator
====================================

Generates accuracy testing template files from consolidated errors/queries data.

This tool:
1. Reads consolidated errors and queries CSV files
2. Parses pipe-delimited incident codes
3. Splits records across multiple templates when they have multiple incident codes
4. Applies appropriate template format based on incident type
5. Creates one template file per incident code

Template formats:
- Buyer validation: 7_35, 7_37, 7_39, 7_66
- Seller validation: 16_19, 16_21, 16_23, 16_20
- Pricing validation: 35_3
- Default format: All other incident codes

Usage:
    from accuracy_template_generator import AccuracyTemplateGenerator
    
    generator = AccuracyTemplateGenerator(
        consolidated_errors="path/to/errors.csv",
        consolidated_queries="path/to/queries.csv"
    )
    
    generator.generate_templates(output_dir="templates/")
"""

import csv
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class IncidentRecord:
    """Represents a single record with its incident codes."""
    incident_codes: List[str]  # Can have multiple codes (pipe-delimited)
    incident_descriptions: List[str]  # Corresponding descriptions
    data_row: List[str]  # Full row from consolidated file


class TemplateFormat:
    """Defines template column structures for different validation types."""
    
    # Buyer validation incidents
    BUYER_INCIDENTS = {'7_35', '7_37', '7_39', '7_66'}
    
    # Seller validation incidents
    SELLER_INCIDENTS = {'16_19', '16_21', '16_23', '16_20'}
    
    # Pricing validation incidents
    PRICING_INCIDENTS = {'35_3'}
    
    # Buyer validation template columns (empty columns to be filled by validation script)
    BUYER_VALIDATION_COLS = [
        "Transaction Reference",
        "Account ID",
        "Person Code",
        "Buyer ID Code",
        "Type of Buyer ID Code",
        "First Name",
        "Surname",
        "Date of Birth",
        "Gender",
        "Prefixed Nationality",
        "Primary Nationality",
        "Secondary Nationality",
        "Correction",
        "Correction Field",
        "Tracker Status"
    ]
    
    # Seller validation template columns
    SELLER_VALIDATION_COLS = [
        "Transaction Reference",
        "Account ID",
        "Person Code",
        "Seller ID Code",
        "Type of Seller ID Code",
        "First Name",
        "Surname",
        "Date of Birth",
        "Gender",
        "Prefixed Nationality",
        "Primary Nationality",
        "Secondary Nationality",
        "Correction",
        "Correction Field",
        "Tracker Status"
    ]
    
    # Pricing validation template columns
    PRICING_VALIDATION_COLS = [
        "Transaction Reference",
        "Error",
        "Net Amount",
        "Consideration",
        "Interest",
        "Total",
        "Expected Interest",
        "Net Difference",
        "Correction",
        "Correction Field"
    ]
    
    # Default template columns
    DEFAULT_VALIDATION_COLS = [
        "Transaction Reference",
        "Account ID",
        "Person Code",
        "Error",
        "Correction",
        "Correction Field"
    ]
    
    # Comparison columns (manual QA) - same for all types
    COMPARISON_COLS = [
        "Agree With Correction",
        "Suggested Correction",
        "Suggested Correction Field"
    ]
    
    @classmethod
    def get_template_type(cls, incident_code: str) -> str:
        """Determine template type for an incident code."""
        if incident_code in cls.BUYER_INCIDENTS:
            return "buyer"
        elif incident_code in cls.SELLER_INCIDENTS:
            return "seller"
        elif incident_code in cls.PRICING_INCIDENTS:
            return "pricing"
        else:
            return "default"
    
    @classmethod
    def get_validation_columns(cls, template_type: str) -> List[str]:
        """Get validation columns for a template type."""
        if template_type == "buyer":
            return cls.BUYER_VALIDATION_COLS.copy()
        elif template_type == "seller":
            return cls.SELLER_VALIDATION_COLS.copy()
        elif template_type == "pricing":
            return cls.PRICING_VALIDATION_COLS.copy()
        else:
            return cls.DEFAULT_VALIDATION_COLS.copy()


class AccuracyTemplateGenerator:
    """Generates accuracy testing template files from consolidated data."""
    
    def __init__(
        self,
        consolidated_errors: Optional[str] = None,
        consolidated_queries: Optional[str] = None
    ):
        """
        Initialize template generator.
        
        Args:
            consolidated_errors: Path to consolidated errors CSV file
            consolidated_queries: Path to consolidated queries CSV file
        """
        self.consolidated_errors = Path(consolidated_errors) if consolidated_errors else None
        self.consolidated_queries = Path(consolidated_queries) if consolidated_queries else None
        self.consolidated_header: List[str] = []
        self.incident_records: Dict[str, List[IncidentRecord]] = defaultdict(list)
    
    def read_consolidated_file(self, file_path: Path) -> List[IncidentRecord]:
        """
        Read consolidated CSV file and parse incident records.
        
        Args:
            file_path: Path to consolidated CSV file
            
        Returns:
            List of IncidentRecord objects
        """
        records = []
        
        with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            header = next(reader)
            
            # Store header if not already set
            if not self.consolidated_header:
                self.consolidated_header = header
            
            # Find incident code and description columns
            try:
                incident_code_idx = header.index('INCIDENT_CODE')
                incident_desc_idx = header.index('INCIDENT_DESCRIPTION')
            except ValueError as e:
                raise ValueError(f"Required column not found in {file_path.name}: {e}")
            
            for row in reader:
                if len(row) <= max(incident_code_idx, incident_desc_idx):
                    continue
                
                # Parse pipe-delimited incident codes
                incident_codes_str = row[incident_code_idx].strip()
                incident_descs_str = row[incident_desc_idx].strip()
                
                if not incident_codes_str or not incident_descs_str:
                    continue
                
                # Split by pipe delimiter
                incident_codes = [code.strip() for code in incident_codes_str.split('|') if code.strip()]
                incident_descs = [desc.strip() for desc in incident_descs_str.split('|') if desc.strip()]
                
                if incident_codes:
                    records.append(IncidentRecord(
                        incident_codes=incident_codes,
                        incident_descriptions=incident_descs,
                        data_row=row
                    ))
        
        return records
    
    def load_consolidated_data(self):
        """Load data from consolidated errors and queries files."""
        print("Loading consolidated data...")
        
        if self.consolidated_errors and self.consolidated_errors.exists():
            print(f"  Reading {self.consolidated_errors.name}...")
            error_records = self.read_consolidated_file(self.consolidated_errors)
            print(f"    Loaded {len(error_records)} records")
            
            # Group by incident code
            for record in error_records:
                for incident_code in record.incident_codes:
                    self.incident_records[incident_code].append(record)
        
        if self.consolidated_queries and self.consolidated_queries.exists():
            print(f"  Reading {self.consolidated_queries.name}...")
            query_records = self.read_consolidated_file(self.consolidated_queries)
            print(f"    Loaded {len(query_records)} records")
            
            # Group by incident code
            for record in query_records:
                for incident_code in record.incident_codes:
                    self.incident_records[incident_code].append(record)
        
        print(f"\nFound {len(self.incident_records)} unique incident codes")
    
    def create_template_header(self, incident_code: str) -> List[str]:
        """
        Create template header row for an incident code.
        
        Args:
            incident_code: Incident code (e.g., "7_37")
            
        Returns:
            List of column names
        """
        template_type = TemplateFormat.get_template_type(incident_code)
        
        # Get validation columns for this template type
        validation_cols = TemplateFormat.get_validation_columns(template_type)
        
        # Add comparison columns
        comparison_cols = TemplateFormat.COMPARISON_COLS.copy()
        
        # Combine: validation columns + comparison columns + consolidated data columns
        header = validation_cols + comparison_cols + self.consolidated_header
        
        return header
    

    
    def create_template_data_rows(self, incident_code: str) -> List[List[str]]:
        """
        Create data rows for template.
        
        Args:
            incident_code: Incident code
            
        Returns:
            List of data rows
        """
        records = self.incident_records.get(incident_code, [])
        template_type = TemplateFormat.get_template_type(incident_code)
        validation_cols = TemplateFormat.get_validation_columns(template_type)
        comparison_cols = TemplateFormat.COMPARISON_COLS
        
        # Find the transaction reference column index in consolidated data
        txn_ref_col_idx = None
        if 'Transaction reference number' in self.consolidated_header:
            txn_ref_col_idx = self.consolidated_header.index('Transaction reference number')
        
        data_rows = []
        
        for record in records:
            # Create validation columns - first column gets transaction reference
            validation_data = [""] * len(validation_cols)
            
            # Copy transaction reference to first validation column
            if txn_ref_col_idx is not None and len(record.data_row) > txn_ref_col_idx:
                validation_data[0] = record.data_row[txn_ref_col_idx]
            
            # Create empty comparison columns
            comparison_data = [""] * len(comparison_cols)
            
            # Append consolidated data
            row = validation_data + comparison_data + record.data_row
            data_rows.append(row)
        
        return data_rows
    
    def generate_template(self, incident_code: str, output_dir: Path, fiscal_year: str = None, quarter: str = None) -> Path:
        """
        Generate template file for an incident code.
        
        Args:
            incident_code: Incident code
            output_dir: Output directory
            fiscal_year: Fiscal year (e.g., "FY25")
            quarter: Quarter (e.g., "Q3")
            
        Returns:
            Path to generated template file
        """
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with FY/Q pattern: "FY25 Q3 7_37.csv"
        if fiscal_year and quarter:
            filename = f"{fiscal_year} {quarter} {incident_code}.csv"
        else:
            filename = f"template_{incident_code}.csv"  # Fallback for backward compatibility
        output_path = output_dir / filename
        
        # Get record count
        record_count = len(self.incident_records.get(incident_code, []))
        
        # Create template
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            header = self.create_template_header(incident_code)
            writer.writerow(header)
            
            # Write data rows
            data_rows = self.create_template_data_rows(incident_code)
            writer.writerows(data_rows)
        
        template_type = TemplateFormat.get_template_type(incident_code)
        print(f"  ✓ {filename} ({template_type} format, {record_count} records)")
        
        return output_path
    
    def generate_templates(self, output_dir: str, fiscal_year: str = None, quarter: str = None) -> Dict[str, Path]:
        """
        Generate all template files.
        
        Args:
            output_dir: Output directory for template files
            fiscal_year: Fiscal year (e.g., "FY25")
            quarter: Quarter (e.g., "Q3")
            
        Returns:
            Dictionary mapping incident codes to template file paths
        """
        output_path = Path(output_dir)
        
        fy_q_label = f"{fiscal_year} {quarter}" if (fiscal_year and quarter) else "templates"
        print(f"\nGenerating {fy_q_label} templates in {output_path}...")
        
        generated_files = {}
        
        # Sort incident codes for consistent output
        for incident_code in sorted(self.incident_records.keys()):
            template_path = self.generate_template(incident_code, output_path, fiscal_year, quarter)
            generated_files[incident_code] = template_path
        
        print(f"\n✓ Generated {len(generated_files)} template files")
        
        return generated_files
    
    def get_summary(self) -> Dict[str, int]:
        """
        Get summary statistics.
        
        Returns:
            Dictionary with summary statistics
        """
        total_records = sum(len(records) for records in self.incident_records.values())
        
        buyer_count = sum(len(records) for code, records in self.incident_records.items() 
                         if code in TemplateFormat.BUYER_INCIDENTS)
        seller_count = sum(len(records) for code, records in self.incident_records.items() 
                          if code in TemplateFormat.SELLER_INCIDENTS)
        pricing_count = sum(len(records) for code, records in self.incident_records.items() 
                           if code in TemplateFormat.PRICING_INCIDENTS)
        default_count = total_records - buyer_count - seller_count - pricing_count
        
        return {
            'total_incidents': len(self.incident_records),
            'total_records': total_records,
            'buyer_records': buyer_count,
            'seller_records': seller_count,
            'pricing_records': pricing_count,
            'default_records': default_count
        }
