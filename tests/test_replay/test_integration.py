#!/usr/bin/env python3
"""
Integration tests for Phase 2 and Phase 3 processors with new correction logic.

These tests verify end-to-end behavior with realistic data files.
"""

import pytest
import sys
import os
import csv
import tempfile
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from replay.phase_2_processor import Phase2Processor
from replay.phase_3_processor import Phase3Processor


class TestPhase2Integration:
    """Integration tests for Phase 2 processor"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for test files"""
        temp_base = tempfile.mkdtemp()
        dirs = {
            'replay_input': os.path.join(temp_base, 'replay'),
            'incident_files': os.path.join(temp_base, 'incidents'),
            'replay_output': os.path.join(temp_base, 'output'),
            'log_output': os.path.join(temp_base, 'logs')
        }
        
        for dir_path in dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        yield dirs
        
        # Cleanup
        shutil.rmtree(temp_base)
    
    def create_incident_file(self, path: str, incident_code: str, data: list):
        """Helper to create incident file"""
        filepath = os.path.join(path, f"FY25 Q4 {incident_code}.csv")
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Header
            writer.writerow(['Transaction Reference', 'Error', 'Correction', 'Correction Field',
                           'Agree With Correction', 'Suggested Correction', 'Suggested Correction Field'])
            # Data
            writer.writerows(data)
        return filepath
    
    def create_replay_file(self, path: str, filename: str, data: list):
        """Helper to create replay file with proper Phase 2 format"""
        filepath = os.path.join(path, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Header - Phase 2 format has 14 columns (0-13)
            header = ['Incident Codes', 'Col1', 'Col2', 'Col3', 'Col4', 'Col5', 
                     'Col6', 'Col7', 'Agrees', 'Correction Field', 'Correction Value',
                     'Col11', 'Col12', 'Transaction Reference']
            writer.writerow(header)
            # Data rows - pad to 14 columns
            for row_data in data:
                # row_data format: [incident_codes, ..., transaction_ref]
                # Create full 14-column row
                full_row = [''] * 14
                full_row[0] = row_data[0]  # Incident Codes
                full_row[13] = row_data[1]  # Transaction Reference (last item)
                writer.writerow(full_row)
        return filepath
    
    def test_phase2_applies_correction_with_agree_y(self, temp_dirs):
        """Test Phase 2 applies correction when Agree = Y"""
        # Create incident file
        incident_data = [
            ['TXN001', 'Y', 'CorrectedValue', 'FieldName', 'Y', '', '']
        ]
        self.create_incident_file(temp_dirs['incident_files'], '7_39', incident_data)
        
        # Create replay file
        replay_data = [
            ['7_39', 'TXN001']  # [incident_code, transaction_ref]
        ]
        self.create_replay_file(temp_dirs['replay_input'], 'test_replay.csv', replay_data)
        
        # Configure processor
        config = {
            'paths': temp_dirs,
            'files': {
                'replay_patterns': ['*.csv'],
                'incident_pattern': 'FY25 Q4 *.csv'
            },
            'incident_columns': {
                'transaction_ref': 'Transaction Reference',
                'error_flag': 'Error',
                'correction': 'Correction',
                'correction_field': 'Correction Field',
                'agree_with_correction': 'Agree With Correction',
                'suggested_correction': 'Suggested Correction',
                'suggested_correction_field': 'Suggested Correction Field'
            },
            'processor': {'batch_size': 50, 'log_level': 'INFO'}
        }
        
        # Process
        processor = Phase2Processor(config_dict=config)
        processor.preload_and_index_incident_files()
        processor.process_replay_file('test_replay.csv')
        
        # Verify output
        output_file = os.path.join(temp_dirs['replay_output'], 'test_replay.csv')
        assert os.path.exists(output_file)
        
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
           # Check data row (skip header)
            assert len(rows) == 2
            # Column 10 = Correction Value, Column 9 = Correction Field (Phase2SingleColumns)
            assert rows[1][10] == 'CorrectedValue'  # Correction Value column
            assert rows[1][9] == 'FieldName'  # Correction Field column
    
    def test_phase2_applies_suggested_when_disagree(self, temp_dirs):
        """Test Phase 2 applies suggested correction when Agree = N"""
        # Create incident file
        incident_data = [
            ['TXN002', 'Y', 'OriginalValue', 'OriginalField', 'N', 
             'SuggestedValue', 'SuggestedField']
        ]
        self.create_incident_file(temp_dirs['incident_files'], '7_40', incident_data)
        
        # Create replay file
        replay_data = [
            ['7_40', 'TXN002']  # [incident_code, transaction_ref]
        ]
        self.create_replay_file(temp_dirs['replay_input'], 'test_replay2.csv', replay_data)
        
        # Configure processor
        config = {
            'paths': temp_dirs,
            'files': {
                'replay_patterns': ['*.csv'],
                'incident_pattern': 'FY25 Q4 *.csv'
            },
            'incident_columns': {
                'transaction_ref': 'Transaction Reference',
                'error_flag': 'Error',
                'correction': 'Correction',
                'correction_field': 'Correction Field',
                'agree_with_correction': 'Agree With Correction',
                'suggested_correction': 'Suggested Correction',
                'suggested_correction_field': 'Suggested Correction Field'
            },
            'processor': {'batch_size': 50, 'log_level': 'INFO'}
        }
        
        # Process
        processor = Phase2Processor(config_dict=config)
        processor.preload_and_index_incident_files()
        processor.process_replay_file('test_replay2.csv')
        
        # Verify output
        output_file = os.path.join(temp_dirs['replay_output'], 'test_replay2.csv')
        assert os.path.exists(output_file)
        
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[1][10] == 'SuggestedValue'
            assert rows[1][9] == 'SuggestedField'
    
    def test_phase2_no_change_when_disagree_no_suggestion(self, temp_dirs):
        """Test Phase 2 returns No Change when Agree = N but no suggestion"""
        # Create incident file
        incident_data = [
            ['TXN003', 'Y', 'OriginalValue', 'OriginalField', 'N', '', '']
        ]
        self.create_incident_file(temp_dirs['incident_files'], '7_41', incident_data)
        
        # Create replay file
        replay_data = [
            ['7_41', 'TXN003']  # [incident_code, transaction_ref]
        ]
        self.create_replay_file(temp_dirs['replay_input'], 'test_replay3.csv', replay_data)
        
        # Configure processor
        config = {
            'paths': temp_dirs,
            'files': {
                'replay_patterns': ['*.csv'],
                'incident_pattern': 'FY25 Q4 *.csv'
            },
            'incident_columns': {
                'transaction_ref': 'Transaction Reference',
                'error_flag': 'Error',
                'correction': 'Correction',
                'correction_field': 'Correction Field',
                'agree_with_correction': 'Agree With Correction',
                'suggested_correction': 'Suggested Correction',
                'suggested_correction_field': 'Suggested Correction Field'
            },
            'processor':{'batch_size': 50, 'log_level': 'INFO'}
        }
        
        # Process
        processor = Phase2Processor(config_dict=config)
        processor.preload_and_index_incident_files()
        processor.process_replay_file('test_replay3.csv')
        
        # Verify output
        output_file = os.path.join(temp_dirs['replay_output'], 'test_replay3.csv')
        assert os.path.exists(output_file)
        
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[1][10] == 'No Change'
            assert rows[1][9] == 'No Change'
    
    def test_phase2_multiple_incident_codes(self, temp_dirs):
        """Test Phase 2 handles multiple incident codes"""
        # Create incident files
        incident_data_1 = [
            ['TXN004', 'Y', 'Value1', 'Field1', 'Y', '', '']
        ]
        self.create_incident_file(temp_dirs['incident_files'], '7_39', incident_data_1)
        
        incident_data_2 = [
            ['TXN004', 'Y', 'Value2', 'Field2', 'P', '', '']
        ]
        self.create_incident_file(temp_dirs['incident_files'], '7_40', incident_data_2)
        
        # Create replay file with multiple incident codes
        replay_data = [
            ['7_39|7_40', 'TXN004']  # [incident_codes, transaction_ref]
        ]
        self.create_replay_file(temp_dirs['replay_input'], 'test_replay4.csv', replay_data)
        
        # Configure processor
        config = {
            'paths': temp_dirs,
            'files': {
                'replay_patterns': ['*.csv'],
                'incident_pattern': 'FY25 Q4 *.csv'
            },
            'incident_columns': {
                'transaction_ref': 'Transaction Reference',
                'error_flag': 'Error',
                'correction': 'Correction',
                'correction_field': 'Correction Field',
                'agree_with_correction': 'Agree With Correction',
                'suggested_correction': 'Suggested Correction',
                'suggested_correction_field': 'Suggested Correction Field'
            },
            'processor': {'batch_size': 50, 'log_level': 'INFO'}
        }
        
        # Process
        processor = Phase2Processor(config_dict=config)
        processor.preload_and_index_incident_files()
        processor.process_replay_file('test_replay4.csv')
        
        # Verify output - should have corrections from both incident codes
        output_file = os.path.join(temp_dirs['replay_output'], 'test_replay4.csv')
        assert os.path.exists(output_file)
        
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 2
            # Should have correction from one of the incident files
            # Column 10 = CORRECTION_VALUE, column 9 = CORRECTION_FIELD
            assert 'Value1' in rows[1][10] or 'Value2' in rows[1][10]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
