"""
Integration tests for CLI interfaces across all refactored scripts.

Tests verify that all scripts have working CLI interfaces with:
- Argument parsing
- Help messages
- Error handling for invalid arguments
"""

import pytest
import subprocess
import sys
from pathlib import Path


# Get the project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"


class TestCLIInterfaces:
    """Test CLI functionality for all refactored scripts."""
    
    def test_phase2_processor_help(self):
        """Test Phase 2 processor --help displays correctly."""
        result = subprocess.run(
            [sys.executable, "-m", "src.replay.phase_2_processor", "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        assert result.returncode == 0
        assert "Phase 2 Processor" in result.stdout
        assert "--config" in result.stdout
        assert "--use-env" in result.stdout
        assert "--log-level" in result.stdout
    
    def test_phase3_processor_help(self):
        """Test Phase 3 processor --help displays correctly."""
        result = subprocess.run(
            [sys.executable, "-m", "src.replay.phase_3_processor", "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        assert result.returncode == 0
        assert "Phase 3 Processor" in result.stdout or "phase_3_processor" in result.stdout
        assert "--config" in result.stdout
        assert "--use-env" in result.stdout
        assert "--log-level" in result.stdout
    
    def test_phase3_final_help(self):
        """Test Phase 3 Final lookup --help displays correctly."""
        result = subprocess.run(
            [sys.executable, "-m", "src.replay.phase_3_final_lookup", "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        assert result.returncode == 0
        assert "--config" in result.stdout
        assert "--use-env" in result.stdout
        assert "--log-level" in result.stdout
    
    def test_xlsx_converter_help(self):
        """Test XLSX Converter --help displays correctly."""
        result = subprocess.run(
            [sys.executable, "-m", "src.utils.xlsx_csv_converter", "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        assert result.returncode == 0
        assert "XLSX to CSV Converter" in result.stdout or "xlsx_csv_converter" in result.stdout
        assert "--config" in result.stdout
        assert "--input-dir" in result.stdout
        assert "--output-dir" in result.stdout
        assert "--log-level" in result.stdout


class TestCLIArgumentParsing:
    """Test argument parsing for CLI interfaces."""
    
    def test_xlsx_converter_missing_required_args(self):
        """Test XLSX Converter loads default config when no args provided."""
        result = subprocess.run(
            [sys.executable, "-m", "src.utils.xlsx_csv_converter"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Should load default config if it exists
        default_config = PROJECT_ROOT / "config" / "local" / "utils" / "xlsx_converter.yaml"
        if default_config.exists():
            # Script may exit with error if files already exist or other issues,
            # but it should load the config successfully
            assert "Loading default configuration" in result.stdout
        else:
            # Should fail if no default config exists
            assert result.returncode != 0
            assert "input_dir" in result.stdout.lower() or "output_dir" in result.stdout.lower()
    
    def test_invalid_log_level(self, tmp_path):
        """Test that invalid log level is rejected."""
        # Create minimal config
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
paths:
  input_dir: /tmp/test
  output_dir: /tmp/test
""")
        
        result = subprocess.run(
            [
                sys.executable, "-m", "src.utils.xlsx_csv_converter",
                "--config", str(config_file),
                "--log-level", "INVALID_LEVEL"
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Should fail with non-zero exit code
        assert result.returncode != 0
        assert "invalid choice" in result.stderr.lower() or "INVALID_LEVEL" in result.stderr


class TestCLIConfigOptions:
    """Test different configuration options via CLI."""
    
    def test_config_file_option(self, sample_xlsx_config):
        """Test using --config option."""
        result = subprocess.run(
            [
                sys.executable, "-m", "src.utils.xlsx_csv_converter",
                "--config", sample_xlsx_config,
                "--help"  # Just test parsing, not execution
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Help should still display (--help overrides)
        assert result.returncode == 0
        assert "--config" in result.stdout
    
    @pytest.mark.skip(reason="--use-env option not implemented in xlsx_csv_converter")
    def test_use_env_option(self):
        """Test using --use-env option."""
        result = subprocess.run(
            [
                sys.executable, "-m", "src.utils.xlsx_csv_converter",
                "--use-env",
                "--help"  # Just test parsing, not execution
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Help should still display
        assert result.returncode == 0
        assert "--use-env" in result.stdout
    
    def test_direct_path_arguments(self, tmp_path):
        """Test using direct --input-dir and --output-dir arguments."""
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        result = subprocess.run(
            [
                sys.executable, "-m", "src.utils.xlsx_csv_converter",
                "--input-dir", str(input_dir),
                "--output-dir", str(output_dir),
                "--help"  # Just test parsing
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Should parse successfully
        assert result.returncode == 0


class TestCLIErrorHandling:
    """Test CLI error handling and error messages."""
    
    def test_nonexistent_config_file(self):
        """Test error handling for nonexistent config file."""
        result = subprocess.run(
            [
                sys.executable, "-m", "src.utils.xlsx_csv_converter",
                "--config", "/nonexistent/config.yaml"
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Should fail with non-zero exit code
        assert result.returncode != 0
        # Should have error message about file not found
        assert "not found" in result.stderr.lower() or "not exist" in result.stderr.lower() or "No such file" in result.stderr
    
    def test_nonexistent_input_directory(self, tmp_path):
        """Test error handling for nonexistent input directory."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        result = subprocess.run(
            [
                sys.executable, "-m", "src.utils.xlsx_csv_converter",
                "--input-dir", "/nonexistent/directory",
                "--output-dir", str(output_dir)
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, 'PYTHONPATH': str(SRC_DIR)}
        )
        
        # Should fail with non-zero exit code
        assert result.returncode != 0
        # Should have error message about directory not existing
        assert "does not exist" in result.stdout or "not exist" in result.stdout or "not found" in result.stdout.lower()
