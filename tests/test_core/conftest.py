"""
Test fixtures and shared utilities
"""

import os
import shutil
import tempfile

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_config_dict():
    """Sample configuration dictionary for testing"""
    return {
        "paths": {
            "replay_input": "/test/input",
            "incident_files": "/test/incident",
            "replay_output": "/test/output",
            "log_output": "/test/logs",
        },
        "processing": {
            "batch_size": 100,
            "log_level": "DEBUG",
            "enable_progress_reporting": True,
            "encoding": "utf-8",
        },
    }


@pytest.fixture
def sample_yaml_config(temp_dir):
    """Create a sample YAML config file for testing"""
    config_content = """
paths:
  replay_input: /test/input
  incident_files: /test/incident
  replay_output: /test/output
  log_output: /test/logs

processing:
  batch_size: 100
  log_level: DEBUG
  enable_progress_reporting: true
  encoding: utf-8
"""
    config_path = os.path.join(temp_dir, "test_config.yaml")
    with open(config_path, "w") as f:
        f.write(config_content)

    return config_path
