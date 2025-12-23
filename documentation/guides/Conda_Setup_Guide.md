# Conda Environment Setup Guide

## Overview

This project uses Conda for package management to ensure compatibility with production environments that have SSL restrictions preventing direct pip/PyPI access.

## Installation Steps

### 1. Install Conda (If Not Already Installed)

If you don't have Conda installed:
- Download Miniconda: https://docs.conda.io/en/latest/miniconda.html
- Or use Anaconda: https://www.anaconda.com/download

### 2. Create Environment from File

```bash
# Navigate to project root
cd /path/to/txr_automation

# Create environment from environment.yml
conda env create -f environment.yml

# This creates an environment named 'txr_automation'
```

### 3. Activate Environment

```bash
conda activate txr_automation
```

You should see `(txr_automation)` in your terminal prompt.

### 4. Verify Installation

```bash
# Check Python version
python --version  # Should be 3.10+

# Check installed packages
conda list

# Run tests
python -m pytest tests/test_core/ -v
```

## Daily Workflow

### Starting Work

```bash
# Activate environment
conda activate txr_automation

# Verify you're in the right environment
conda info --envs  # * indicates active environment
```

### Running Scripts

```bash
# Make sure environment is activated first
conda activate txr_automation

# Run your scripts
python src/replay/phase_2_processor.py --config config/environments/phase2.yaml
```

### Running Tests

```bash
conda activate txr_automation
python -m pytest tests/ -v
```

## Managing the Environment

### Update Environment

If `environment.yml` changes:

```bash
# Update existing environment
conda env update -f environment.yml --prune
```

### Add New Package

To add a new package to the project:

1. Add it to `environment.yml`:
   ```yaml
   dependencies:
     - python>=3.10
     - pyyaml>=6.0
     - pandas>=2.0.0  # NEW PACKAGE
   ```

2. Update environment:
   ```bash
   conda env update -f environment.yml --prune
   ```

### Export Current Environment

To capture exact versions currently installed:

```bash
# Export with exact versions
conda env export > environment-lock.yml

# Or just the explicitly installed packages
conda env export --from-history > environment.yml
```

### Remove Environment

If you need to start fresh:

```bash
# Deactivate first
conda deactivate

# Remove environment
conda env remove -n txr_automation

# Recreate
conda env create -f environment.yml
```

## Troubleshooting

### "Conda: command not found"

Add Conda to your PATH:

```bash
# Add to ~/.zshrc or ~/.bash_profile
export PATH="$HOME/miniconda3/bin:$PATH"

# Or initialize conda
conda init zsh  # or bash
```

### SSL Certificate Errors

Conda should work behind SSL restrictions. If you still have issues:

```bash
# Add channels without SSL verification (last resort)
conda config --set ssl_verify false
```

### Package Not Found

Try adding conda-forge channel:

```bash
conda config --add channels conda-forge
conda config --set channel_priority strict
```

### Environment Activation Not Working

```bash
# Initialize conda for your shell
conda init zsh  # or bash

# Restart terminal
# Try activating again
conda activate txr_automation
```

## Production Deployment

### On Restricted Machines

1. **Copy project to machine**:
   ```bash
   # Use approved file transfer method
   ```

2. **Ensure Conda is installed** (usually pre-installed on enterprise machines)

3. **Create environment**:
   ```bash
   cd /path/to/txr_automation
   conda env create -f environment.yml
   ```

4. **Activate and verify**:
   ```bash
   conda activate txr_automation
   python -m pytest tests/test_core/ -v
   ```

5. **Configure paths**:
   ```bash
   cp config/templates/phase2_template.yaml config/environments/phase2.yaml
   # Edit config/environments/phase2.yaml with production paths
   ```

6. **Run scripts**:
   ```bash
   python src/replay/phase_2_processor.py --config config/environments/phase2.yaml
   ```

## Environment File Structure

### environment.yml (Main File)

```yaml
name: txr_automation
channels:
  - defaults
  - conda-forge
dependencies:
  - python>=3.10        # Python version
  - pyyaml>=6.0        # YAML config files
  - pytest>=7.4.0      # Testing framework
  - pytest-cov>=4.1.0  # Coverage reporting
  - pip                # For pip packages if needed
  - pip:
    - -e .             # Install project in editable mode
```

### Why This Structure?

- **channels**: Where to get packages from
- **dependencies**: Packages to install
- **pip section**: For packages not available in Conda (like this project itself)
- **-e .**: Installs project in "editable" mode so code changes are immediately available

## Best Practices

### DO ✅

- Always activate environment before running scripts
- Update environment.yml when adding dependencies
- Test changes with `python -m pytest tests/`
- Commit environment.yml changes to git

### DON'T ❌

- Don't use `pip install` directly (use conda)
- Don't mix conda and system Python
- Don't forget to activate environment
- Don't commit environment-lock.yml (too specific)

## Quick Reference

| Task | Command |
|------|---------|
| Create environment | `conda env create -f environment.yml` |
| Activate environment | `conda activate txr_automation` |
| Deactivate environment | `conda deactivate` |
| List environments | `conda env list` |
| Update environment | `conda env update -f environment.yml --prune` |
| Remove environment | `conda env remove -n txr_automation` |
| List packages | `conda list` |
| Run tests | `python -m pytest tests/ -v` |

## Integration with Scripts

All scripts work normally once environment is activated:

```bash
conda activate txr_automation

# Run scripts
python src/replay/phase_2_processor.py --config config/environments/phase2.yaml
python src/replay/phase_3_processor.py --config config/environments/phase3.yaml
python src/utils/xlsx_csv_converter.py input.xlsx output.csv

# Run tests
./scripts/run_tests.sh

# Run with coverage
./scripts/run_tests_with_coverage.sh
```

## Support

For issues with:
- **Conda itself**: See https://docs.conda.io/
- **This project**: See README.md or contact the team
- **SSL restrictions**: Contact your IT department
