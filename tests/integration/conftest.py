"""
Pytest fixtures for integration tests.
"""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary directory for test configuration files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary directory for test data files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create subdirectories
    (data_dir / "input").mkdir()
    (data_dir / "output").mkdir()
    (data_dir / "logs").mkdir()
    (data_dir / "incident").mkdir()

    return data_dir


@pytest.fixture
def sample_phase2_config(temp_config_dir, temp_data_dir):
    """Create a sample Phase 2 configuration file."""
    config_content = f"""
paths:
  replay_input: {temp_data_dir / "input"}
  incident_files: {temp_data_dir / "incident"}
  replay_output: {temp_data_dir / "output"}
  log_output: {temp_data_dir / "logs"}

processing:
  batch_size: 50
  log_level: INFO

replace_pattern:
  old: "KR"
  new: "AJB"
"""
    config_file = temp_config_dir / "phase2_test.yaml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def sample_phase3_config(temp_config_dir, temp_data_dir):
    """Create a sample Phase 3 configuration file."""
    config_content = f"""
paths:
  replay_input: {temp_data_dir / "input"}
  incident_files: {temp_data_dir / "incident"}
  replay_output: {temp_data_dir / "output"}
  log_output: {temp_data_dir / "logs"}

processing:
  batch_size: 100
  similarity_threshold: 0.85
  log_level: INFO

replay_files:
  - "inconsistent_buyer_ids.csv"
  - "inconsistent_seller_ids.csv"
  - "inconsistent_buyer_names.csv"
  - "inconsistent_seller_names.csv"

replace_pattern:
  old: "KR"
  new: "AJB"
"""
    config_file = temp_config_dir / "phase3_test.yaml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def sample_phase3_final_config(temp_config_dir, temp_data_dir):
    """Create a sample Phase 3 Final configuration file."""
    config_content = f"""
paths:
  base_path: {temp_data_dir}
  data_reference: {temp_data_dir / "input"}
  output: {temp_data_dir / "output"}
  log_output: {temp_data_dir / "logs"}

file_patterns:
  unavista_pattern: "UnaVista*.csv"
  replay_ids_pattern: "*_ids_replay*.csv"
  replay_names_pattern: "*_names_replay*.csv"

processing:
  skip_duplicates: true
  log_level: INFO
"""
    config_file = temp_config_dir / "phase3_final_test.yaml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def sample_xlsx_config(temp_config_dir, temp_data_dir):
    """Create a sample XLSX Converter configuration file."""
    config_content = f"""
paths:
  input_dir: {temp_data_dir / "input"}
  output_dir: {temp_data_dir / "output"}
  log_output: {temp_data_dir / "logs"}

processing:
  encoding: utf-8-sig
  split_multiline: true

logging:
  level: INFO
  structured: true
"""
    config_file = temp_config_dir / "xlsx_converter_test.yaml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def clean_env():
    """Clean environment variables before and after tests."""
    # Save original environment
    original_env = os.environ.copy()

    # Remove TXR_* variables
    for key in list(os.environ.keys()):
        if key.startswith("TXR_"):
            del os.environ[key]

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
