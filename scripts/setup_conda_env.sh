#!/bin/bash
# Setup script for Conda environment

echo "TXR Automation - Conda Environment Setup"
echo "========================================="
echo

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "ERROR: Conda is not installed or not in PATH"
    echo "Please install Miniconda or Anaconda first"
    echo "See: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo "✓ Conda found: $(conda --version)"
echo

# Check if environment already exists
if conda env list | grep -q "^txr_automation "; then
    echo "Environment 'txr_automation' already exists"
    read -p "Do you want to update it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Updating environment..."
        conda env update -f environment.yml --prune
        echo "✓ Environment updated"
    else
        echo "Skipping update"
    fi
else
    echo "Creating new environment..."
    conda env create -f environment.yml
    echo "✓ Environment created"
fi

echo
echo "========================================="
echo "Setup complete!"
echo
echo "To activate the environment, run:"
echo "  conda activate txr_automation"
echo
echo "To verify installation, run:"
echo "  conda activate txr_automation"
echo "  python -m pytest tests/test_core/ -v"
echo
